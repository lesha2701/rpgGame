"""Computes a quest's current progress by querying whichever existing table
that QuestConditionType is actually about. This is the one place that maps
condition_type -> query — quest_service.py never runs its own SQL for this,
and Battle/UserExpedition/ChestOpening/skill_service/inventory_service never
need to know quests exist (see QuestConditionType's docstring and
ARCHITECTURE.md's Stage 8 section for the full "reads, never writes"
rationale). Not a pure function in the progression.py/item_progression.py
sense (it needs a DB session to count rows) — "service-level" is the more
accurate description, kept in its own module anyway so this branching logic
doesn't get folded into quest_service's claim/list orchestration."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.arena_match import ArenaMatch
from app.models.battle import Battle
from app.models.character_skill import CharacterSkill
from app.models.chest_opening import ChestOpening
from app.models.enums import ArenaMatchStatus, BattleResult, ExpeditionStatus, QuestConditionType
from app.models.quest_definition import QuestDefinition
from app.models.user_campaign_node_clear import UserCampaignNodeClear
from app.models.user_expedition import UserExpedition
from app.models.user_hero import UserHero
from app.models.user_item import UserItem


async def _count_battles_won(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count(Battle.id)).where(Battle.user_id == user_id, Battle.result == BattleResult.won)
    )
    return result.scalar_one()


async def _count_expeditions_claimed(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count(UserExpedition.id)).where(
            UserExpedition.user_id == user_id, UserExpedition.status == ExpeditionStatus.claimed
        )
    )
    return result.scalar_one()


async def _count_chests_opened(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(select(func.count(ChestOpening.id)).where(ChestOpening.user_id == user_id))
    return result.scalar_one()


async def _count_items_equipped(db: AsyncSession, hero_id: int) -> int:
    result = await db.execute(select(func.count(UserItem.id)).where(UserItem.equipped_hero_id == hero_id))
    return result.scalar_one()


async def _count_skills_upgraded(db: AsyncSession, hero_id: int) -> int:
    """Sum of every learned skill's level, not the count of distinct
    skills learned — a class only ever has 3 skills (Stage 3), so "5
    distinct skills" could never be reached. CharacterSkill.level only ever
    increases (skill_service.upgrade_skill), so this sum is exactly the
    lifetime count of upgrade actions taken — same shape as skill_service.
    _spent_skill_points, computed independently here rather than reaching
    into that module's private helper."""
    result = await db.execute(
        select(func.coalesce(func.sum(CharacterSkill.level), 0)).where(CharacterSkill.hero_id == hero_id)
    )
    return result.scalar_one()


async def _count_arena_wins(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count(ArenaMatch.id)).where(
            ArenaMatch.status == ArenaMatchStatus.finished, ArenaMatch.winner_user_id == user_id
        )
    )
    return result.scalar_one()


async def _count_campaign_nodes_cleared(db: AsyncSession, user_id: int) -> int:
    # Distinct nodes cleared at least once — a repeat clear of the same
    # node doesn't count again, matching how battles_won already counts
    # distinct victories rather than distinct enemies.
    result = await db.execute(
        select(func.count(UserCampaignNodeClear.id)).where(UserCampaignNodeClear.user_id == user_id)
    )
    return result.scalar_one()


async def get_quest_progress(
    db: AsyncSession, user_id: int, hero: UserHero | None, quest_definition: QuestDefinition
) -> int:
    """hero-scoped condition types (hero_level/items_equipped/
    skills_upgraded) return 0 when the user has no active hero — you can't
    have equipped an item or upgraded a skill without one. user-scoped
    types (battles_won/expeditions_claimed/chests_opened) don't need a
    hero at all, matching how those tables are keyed (ChestOpening has no
    hero_id column — chests are a user-level currency spend, not a
    hero-level one)."""
    condition_type = quest_definition.condition_type

    if condition_type == QuestConditionType.battles_won:
        return await _count_battles_won(db, user_id)
    if condition_type == QuestConditionType.expeditions_claimed:
        return await _count_expeditions_claimed(db, user_id)
    if condition_type == QuestConditionType.chests_opened:
        return await _count_chests_opened(db, user_id)
    if condition_type == QuestConditionType.hero_level:
        return hero.level if hero is not None else 0
    if condition_type == QuestConditionType.items_equipped:
        return await _count_items_equipped(db, hero.id) if hero is not None else 0
    if condition_type == QuestConditionType.skills_upgraded:
        return await _count_skills_upgraded(db, hero.id) if hero is not None else 0
    if condition_type == QuestConditionType.arena_wins:
        return await _count_arena_wins(db, user_id)
    if condition_type == QuestConditionType.campaign_nodes_cleared:
        return await _count_campaign_nodes_cleared(db, user_id)

    raise ValueError(f"Unhandled QuestConditionType: {condition_type}")  # pragma: no cover
