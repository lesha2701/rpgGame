"""Quest orchestration — list/claim only. Deliberately does NOT call into
Battle/Expedition/Chest services, and they never call into this one: quest
progress is read directly off their tables by quest_progression.py, one
direction only. See QuestDefinition/UserQuest's docstrings for the full
"reads, never writes, no event bus" rationale.

Slot rotation (ACTIVE_QUEST_SLOT_COUNT active at a time, refilled from the
catalog on claim) mirrors the football app's task-slot mechanic, with one
deliberate simplification: each QuestDefinition is drawn for a given user
AT MOST ONCE ever (no metric_baseline, no reassignment) — see UserQuest's
docstring for why. A claimed quest is never deleted, so `list_quests`
naturally returns a permanent, growing history alongside the live slots."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import TransactionType
from app.models.quest_definition import QuestDefinition
from app.models.user import User
from app.models.user_hero import UserHero
from app.models.user_quest import UserQuest
from app.schemas.quest import QuestClaimOut, QuestOut
from app.services.hero_service import hero_progress_out
from app.services.quest_progression import get_quest_progress
from app.services.reward_service import grant_hero_reward

# How many quests are ever active/visible-to-progress at once — the rest
# of the (potentially much larger) QuestDefinition catalog just waits in
# the pool. One named constant, read from exactly one place, same
# discipline as campaign_battle_service.REPEAT_CLEAR_REWARD_FRACTION.
ACTIVE_QUEST_SLOT_COUNT = 5


async def _ensure_slots_filled(db: AsyncSession, user_id: int) -> None:
    """Draws a random not-yet-assigned-to-this-user active QuestDefinition
    into every empty slot (0..ACTIVE_QUEST_SLOT_COUNT-1). Safe to call on
    every list_quests()/claim_quest(): a no-op once every slot is full or
    the pool is exhausted. The IntegrityError catch handles two concurrent
    calls racing to fill the same slot for the same user — the loser rolls
    back and whatever slots are still empty get picked up on the next
    call; nothing rewarding is at stake here."""
    result = await db.execute(select(UserQuest).where(UserQuest.user_id == user_id))
    rows = result.scalars().all()
    used_definition_ids = {row.quest_definition_id for row in rows}
    occupied_slots = {row.slot_index for row in rows if row.slot_index is not None}
    empty_slots = [i for i in range(ACTIVE_QUEST_SLOT_COUNT) if i not in occupied_slots]
    if not empty_slots:
        return

    now = datetime.now(timezone.utc)
    changed = False
    for slot_index in empty_slots:
        conditions = [QuestDefinition.is_active.is_(True)]
        if used_definition_ids:
            conditions.append(QuestDefinition.id.notin_(used_definition_ids))
        result = await db.execute(select(QuestDefinition).where(*conditions).order_by(func.random()).limit(1))
        definition = result.scalar_one_or_none()
        if definition is None:
            continue  # pool exhausted — fewer active definitions than slots
        db.add(
            UserQuest(
                user_id=user_id, quest_definition_id=definition.id, slot_index=slot_index, claimed_at=None, created_at=now
            )
        )
        used_definition_ids.add(definition.id)
        changed = True

    if not changed:
        return
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()


def _quest_out(row: UserQuest, definition: QuestDefinition, progress: int) -> QuestOut:
    return QuestOut(
        id=row.id,
        code=definition.code,
        name=definition.name,
        description=definition.description,
        condition_type=definition.condition_type.value,
        target_value=definition.target_value,
        current_progress=progress,
        is_completed=progress >= definition.target_value,
        is_claimed=row.claimed_at is not None,
        is_active_slot=row.slot_index is not None,
        reward_xp=definition.reward_xp,
        reward_coins=definition.reward_coins,
    )


async def list_quests(db: AsyncSession, user: User, hero: UserHero | None) -> list[QuestOut]:
    await _ensure_slots_filled(db, user.id)

    result = await db.execute(select(UserQuest).where(UserQuest.user_id == user.id))
    rows = [row for row in result.scalars().all() if row.quest_definition.is_active]
    # Active slots first (in slot order), then history — newest claim first.
    rows.sort(
        key=lambda row: (
            0 if row.slot_index is not None else 1,
            row.slot_index if row.slot_index is not None else 0,
            -(row.claimed_at.timestamp() if row.claimed_at else 0),
        )
    )

    out = []
    for row in rows:
        progress = await get_quest_progress(db, user.id, hero, row.quest_definition)
        out.append(_quest_out(row, row.quest_definition, progress))
    return out


async def _lock_owned_user_quest_or_404(db: AsyncSession, user_id: int, user_quest_id: int) -> UserQuest:
    # of=UserQuest: quest_definition is lazy="joined", same outer-join FOR
    # UPDATE gotcha documented on hero_service.lock_hero_for_update.
    result = await db.execute(
        select(UserQuest)
        .where(UserQuest.id == user_quest_id, UserQuest.user_id == user_id)
        .with_for_update(of=UserQuest)
        .execution_options(populate_existing=True)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFoundError("Quest not found")
    return row


async def claim_quest(db: AsyncSession, user: User, hero: UserHero, user_quest_id: int) -> QuestClaimOut:
    """Unlike expedition claims, a repeat claim here is a genuine 409, not
    an idempotent replay — matches the football app's claim_task_reward,
    which also errors on an already-claimed task rather than silently
    re-confirming it. Concurrency-safe the same way expedition claims are:
    lock this one row, re-check its state after the lock is held, so two
    concurrent claims on the same id serialize on that lock and the loser
    sees claimed_at already set (raising 409) rather than granting
    anything twice — no idempotency-key needed, this operates on a row
    that already exists and already has an id."""
    locked_row = await _lock_owned_user_quest_or_404(db, user.id, user_quest_id)

    if locked_row.claimed_at is not None:
        raise ConflictError("Reward for this quest has already been claimed")

    definition = locked_row.quest_definition
    progress = await get_quest_progress(db, user.id, hero, definition)
    if progress < definition.target_value:
        raise ConflictError(
            "Quest is not completed yet",
            details={"current_progress": progress, "target_value": definition.target_value},
        )

    locked_hero, locked_user = await grant_hero_reward(
        db,
        hero.id,
        user.id,
        definition.reward_xp,
        definition.reward_coins,
        TransactionType.quest_reward,
        f"Задание «{definition.name}»",
        related_object_type="user_quest",
        related_object_id=locked_row.id,
    )

    now = datetime.now(timezone.utc)
    locked_row.claimed_at = now
    # Frees the slot — the claimed quest itself stays in the user's
    # permanent history (its row is never deleted), a replacement is
    # drawn into this same slot_index below.
    locked_row.slot_index = None
    db.add(locked_row)
    await db.commit()

    # Best-effort, separate from the reward-granting commit above: if this
    # somehow doesn't run, the next list_quests() call refills it anyway.
    await _ensure_slots_filled(db, user.id)

    return QuestClaimOut(
        id=locked_row.id,
        code=definition.code,
        name=definition.name,
        reward_xp=definition.reward_xp,
        reward_coins=definition.reward_coins,
        claimed_at=now.isoformat(),
        hero_progress=hero_progress_out(locked_hero, locked_user),
    )
