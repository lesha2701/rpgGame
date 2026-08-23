"""Expeditions: hero commits for a fixed duration, then the player claims a
fixed XP+coins reward. No background worker exists or is needed — every
check is a pure timestamp comparison against `UserExpedition.completed_at`,
computed once at start() and frozen from then on (see that model's
docstring). If the server is down for the whole duration, the very next
`claim()` request still resolves correctly, because nothing about the check
depends on a process having been running while time passed.

Reused from the football app (see ARCHITECTURE.md's Stage 7 section for the
full comparison): free_pack_service.py's `_is_available()` timestamp-vs-now
pattern is the direct ancestor of `_is_time_complete()` below — the same
"compute availability from a stored deadline, no scheduler" shape, just
applied to a hero's expedition instead of a per-user pack cooldown."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.timeutil import ensure_aware
from app.models.enums import ExpeditionStatus, TransactionType
from app.models.expedition_template import ExpeditionTemplate
from app.models.user import User
from app.models.user_expedition import UserExpedition
from app.models.user_hero import UserHero
from app.schemas.expedition import ExpeditionSummaryOut, ExpeditionTemplateOut, UserExpeditionOut
from app.services.hero_service import hero_progress_out, lock_hero_for_update
from app.services.reward_service import grant_hero_reward


async def _get_template_or_404(db: AsyncSession, expedition_template_id: int) -> ExpeditionTemplate:
    template = await db.get(ExpeditionTemplate, expedition_template_id)
    if template is None:
        raise NotFoundError("Expedition not found")
    return template


def _assert_template_active(template: ExpeditionTemplate) -> None:
    if not template.is_active:
        raise ConflictError("This expedition is not currently available")


async def list_templates(db: AsyncSession) -> list[ExpeditionTemplate]:
    result = await db.execute(
        select(ExpeditionTemplate)
        .where(ExpeditionTemplate.is_active.is_(True))
        .order_by(ExpeditionTemplate.sort_order, ExpeditionTemplate.id)
    )
    return list(result.scalars().all())


def template_to_out(template: ExpeditionTemplate, hero_level: Optional[int]) -> ExpeditionTemplateOut:
    return ExpeditionTemplateOut(
        id=template.id,
        name=template.name,
        description=template.description,
        image_path=template.image_path,
        duration_seconds=template.duration_seconds,
        required_hero_level=template.required_hero_level,
        reward_xp=template.reward_xp,
        reward_coins=template.reward_coins,
        is_active=template.is_active,
        is_available_to_user=(hero_level is not None and hero_level >= template.required_hero_level),
    )


def _is_time_complete(row: UserExpedition, now: datetime) -> bool:
    return now >= ensure_aware(row.completed_at)


def _status_out(row: UserExpedition, now: datetime) -> str:
    if row.status == ExpeditionStatus.claimed:
        return "claimed"
    return "completed" if _is_time_complete(row, now) else "running"


async def _build_out(row: UserExpedition, hero: UserHero, user: User) -> UserExpeditionOut:
    now = datetime.now(timezone.utc)
    # See hero_progress_out's docstring — same shared computation Battle
    # uses, pulled apart into this response's own already-shipped flat
    # field names rather than nesting HeroProgressOut directly.
    progress = hero_progress_out(hero, user)
    return UserExpeditionOut(
        id=row.id,
        expedition=ExpeditionSummaryOut(id=row.expedition_template.id, name=row.expedition_template.name),
        status=_status_out(row, now),
        started_at=row.started_at.isoformat(),
        completed_at=row.completed_at.isoformat(),
        claimed_at=row.claimed_at.isoformat() if row.claimed_at else None,
        reward_xp=row.reward_xp,
        reward_coins=row.reward_coins,
        hero_level=progress.level,
        hero_xp=progress.xp,
        balance=progress.balance,
    )


async def _get_running_expedition_row(db: AsyncSession, hero_id: int) -> Optional[UserExpedition]:
    result = await db.execute(
        select(UserExpedition).where(
            UserExpedition.hero_id == hero_id, UserExpedition.status == ExpeditionStatus.running
        )
    )
    return result.scalar_one_or_none()


async def get_current_expedition(db: AsyncSession, hero: UserHero, user: User) -> Optional[UserExpeditionOut]:
    row = await _get_running_expedition_row(db, hero.id)
    if row is None:
        return None
    return await _build_out(row, hero, user)


async def start_expedition(
    db: AsyncSession, user: User, hero: UserHero, expedition_template_id: int
) -> UserExpeditionOut:
    template = await _get_template_or_404(db, expedition_template_id)
    _assert_template_active(template)

    # Lock the hero row FIRST: this is what makes "check for an existing
    # running expedition, then insert one" atomic against a second
    # concurrent start for the same hero (same pattern as Stage 4's
    # equip_item locking the hero row before checking/swapping the
    # occupied slot). The partial unique index on the table is defense in
    # depth behind this, not the primary mechanism.
    locked_hero = await lock_hero_for_update(db, hero.id)

    if locked_hero.level < template.required_hero_level:
        raise ConflictError(
            "Hero level too low for this expedition",
            details={"hero_level": locked_hero.level, "required_hero_level": template.required_hero_level},
        )

    # No separate "hero is mid-battle" check: Battle rows in this backend
    # are only ever created already-resolved (see ARCHITECTURE.md's Stage 6
    # section) — there is no persisted in-progress battle state for a hero
    # to be caught in across requests, so that half of the busy-check is
    # vacuously satisfied by Stage 6's design rather than needing its own
    # query here.
    if await _get_running_expedition_row(db, locked_hero.id) is not None:
        raise ConflictError("Hero is already on an expedition")

    now = datetime.now(timezone.utc)
    row = UserExpedition(
        user_id=user.id,
        hero_id=locked_hero.id,
        expedition_template_id=template.id,
        status=ExpeditionStatus.running,
        started_at=now,
        completed_at=now + timedelta(seconds=template.duration_seconds),
        claimed_at=None,
        # Snapshotted now, not read live from the template at claim time —
        # see UserExpedition's docstring for why.
        reward_xp=template.reward_xp,
        reward_coins=template.reward_coins,
        created_at=now,
    )
    db.add(row)

    try:
        await db.commit()
    except IntegrityError:
        # The partial unique index catching a race the hero-row lock above
        # should already have prevented — belt and suspenders, not the
        # expected path. No idempotency-replay here (unlike chest/battle
        # start): starting isn't naturally retryable the way a purchase is,
        # so the loser just fails cleanly instead of adopting the winner's
        # expedition.
        await db.rollback()
        raise ConflictError("Hero is already on an expedition")

    return await _build_out(row, locked_hero, user)


async def _lock_owned_expedition_or_404(db: AsyncSession, user_id: int, user_expedition_id: int) -> UserExpedition:
    # of=UserExpedition: expedition_template is lazy="joined", and Postgres
    # rejects FOR UPDATE on the nullable side of the outer join that would
    # otherwise try to lock through — same fix as hero_service.
    # lock_hero_for_update (see that function's docstring for the full
    # explanation of why this is needed).
    result = await db.execute(
        select(UserExpedition)
        .where(UserExpedition.id == user_expedition_id, UserExpedition.user_id == user_id)
        .with_for_update(of=UserExpedition)
        .execution_options(populate_existing=True)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFoundError("Expedition not found")
    return row


async def claim_expedition(
    db: AsyncSession, user: User, hero: UserHero, user_expedition_id: int
) -> UserExpeditionOut:
    """Idempotent by construction: this operates on an EXISTING row
    (identified by its own id), not a fresh create, so there's no need for
    an idempotency-key/unique-constraint dance like chest/battle opens use.
    Locking the row (`FOR UPDATE`) and checking its CURRENT status after
    the lock is acquired is sufficient — two concurrent claims on the same
    id serialize on that lock; whichever acquires it second sees
    status=claimed already (the first committed before releasing the lock)
    and returns that result without granting anything a second time."""
    locked_row = await _lock_owned_expedition_or_404(db, user.id, user_expedition_id)

    if locked_row.status == ExpeditionStatus.claimed:
        return await _build_out(locked_row, hero, user)

    now = datetime.now(timezone.utc)
    if not _is_time_complete(locked_row, now):
        raise ConflictError(
            "Expedition is not completed yet",
            details={"completes_at": locked_row.completed_at.isoformat()},
        )

    locked_hero, locked_user = await grant_hero_reward(
        db,
        locked_row.hero_id,
        user.id,
        locked_row.reward_xp,
        locked_row.reward_coins,
        TransactionType.expedition_reward,
        f"Экспедиция «{locked_row.expedition_template.name}»",
        related_object_type="user_expedition",
        related_object_id=locked_row.id,
    )

    locked_row.status = ExpeditionStatus.claimed
    locked_row.claimed_at = now
    db.add(locked_row)

    await db.commit()
    return await _build_out(locked_row, locked_hero, locked_user)


async def list_history(db: AsyncSession, hero: UserHero, user: User, limit: int = 50) -> list[UserExpeditionOut]:
    result = await db.execute(
        select(UserExpedition).where(UserExpedition.user_id == user.id).order_by(UserExpedition.id.desc()).limit(limit)
    )
    rows = result.scalars().all()
    return [await _build_out(row, hero, user) for row in rows]
