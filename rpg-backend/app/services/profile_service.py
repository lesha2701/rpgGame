"""Profile: pure read-side aggregation, no mutation, no locking (nothing
here needs FOR UPDATE — a snapshot read under Postgres's default
transaction isolation is exactly what "current statistics" means). Every
number in `get_statistics` is computed from tables that already exist —
Battle/ArenaMatch/UserExpedition/UserQuest/ChestOpening/User — the same
"derive, don't store" call this project has made at every prior stage,
applied here to cross-feature aggregates instead of a single feature's own
progress. See ARCHITECTURE.md's Stage 11 section for why none of these
numbers get a stored counter column."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.arena_match import ArenaMatch
from app.models.battle import Battle
from app.models.character_skill import CharacterSkill
from app.models.chest_opening import ChestOpening
from app.models.enums import ArenaMatchStatus, BattleResult, ExpeditionStatus
from app.models.user import User
from app.models.user_campaign_node_clear import UserCampaignNodeClear
from app.models.user_expedition import UserExpedition
from app.models.user_hero import UserHero
from app.models.user_item import UserItem
from app.models.user_quest import UserQuest
from app.schemas.profile import (
    ArenaStatsOut,
    BattleStatsOut,
    CampaignStatsOut,
    ChestStatsOut,
    ExpeditionStatsOut,
    HeroActivityStatsOut,
    ProfileOut,
    ProfileStatisticsOut,
    PublicHeroOut,
    PublicProfileOut,
    PublicStatisticsOut,
    QuestStatsOut,
    ReferralStatsOut,
)
from app.services.hero_service import get_active_hero, hero_to_out
from app.services.referral_service import referral_count as get_referral_count
from app.services.referral_service import total_referred_count


async def _build_user_me_out(db: AsyncSession, user: User):
    # Deferred import: routers/auth.py owns UserMeOut's canonical builder;
    # duplicating these ~4 lines here (rather than importing a router
    # function into a service, which would invert the dependency
    # direction) is the smaller cost. See ARCHITECTURE.md's Stage 11
    # section.
    from app.schemas.auth import UserMeOut

    hero = await get_active_hero(db, user)
    return UserMeOut(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        active_hero=await hero_to_out(db, hero) if hero else None,
        referral_code=str(user.telegram_id),
        referral_count=await get_referral_count(db, user.id),
    )


async def get_statistics(db: AsyncSession, user_id: int, hero_id: int | None = None) -> ProfileStatisticsOut:
    """One round trip: independent scalar subqueries in a single SELECT
    with no FROM clause, each aggregating its own table in isolation — not
    a single query that JOINs tables together (which would multiply rows
    across every one-to-many relationship involved) and not one
    `await db.execute()` call per number either. Losses are computed in
    Python as played-wins, needing no separate query — Battle has no third
    "draw" result, and a finished ArenaMatch always has a winner (see
    BattleResult/ArenaMatchStatus docstrings), so this subtraction is
    exact, not an approximation.

    `hero_id` is optional (None for a user with no active hero, same
    "return 0" convention quest_progression.get_quest_progress already
    uses for hero-scoped condition types) — items_equipped/skills_upgraded
    are the two hero-scoped numbers here."""
    battles_played_sq = select(func.count(Battle.id)).where(Battle.user_id == user_id).scalar_subquery()
    battles_won_sq = (
        select(func.count(Battle.id))
        .where(Battle.user_id == user_id, Battle.result == BattleResult.won)
        .scalar_subquery()
    )
    arena_played_sq = (
        select(func.count(ArenaMatch.id))
        .where(
            ArenaMatch.status == ArenaMatchStatus.finished,
            (ArenaMatch.player_a_user_id == user_id) | (ArenaMatch.player_b_user_id == user_id),
        )
        .scalar_subquery()
    )
    arena_won_sq = select(func.count(ArenaMatch.id)).where(ArenaMatch.winner_user_id == user_id).scalar_subquery()
    expeditions_started_sq = (
        select(func.count(UserExpedition.id)).where(UserExpedition.user_id == user_id).scalar_subquery()
    )
    expeditions_claimed_sq = (
        select(func.count(UserExpedition.id))
        .where(UserExpedition.user_id == user_id, UserExpedition.status == ExpeditionStatus.claimed)
        .scalar_subquery()
    )
    quests_claimed_sq = (
        select(func.count(UserQuest.id))
        .where(UserQuest.user_id == user_id, UserQuest.claimed_at.is_not(None))
        .scalar_subquery()
    )
    chests_opened_sq = select(func.count(ChestOpening.id)).where(ChestOpening.user_id == user_id).scalar_subquery()
    referred_total_sq = select(func.count(User.id)).where(User.referred_by_id == user_id).scalar_subquery()
    referred_successful_sq = (
        select(func.count(User.id))
        .where(User.referred_by_id == user_id, User.referral_reward_granted.is_(True))
        .scalar_subquery()
    )
    campaign_nodes_cleared_sq = (
        select(func.count(UserCampaignNodeClear.id)).where(UserCampaignNodeClear.user_id == user_id).scalar_subquery()
    )
    campaign_total_clears_sq = (
        select(func.coalesce(func.sum(UserCampaignNodeClear.clear_count), 0))
        .where(UserCampaignNodeClear.user_id == user_id)
        .scalar_subquery()
    )
    # hero-scoped: 0 when the user has no active hero, same convention
    # quest_progression.get_quest_progress uses for these two.
    items_equipped_sq = (
        select(func.count(UserItem.id)).where(UserItem.equipped_hero_id == hero_id).scalar_subquery()
        if hero_id is not None
        else select(0).scalar_subquery()
    )
    skills_upgraded_sq = (
        select(func.coalesce(func.sum(CharacterSkill.level), 0)).where(CharacterSkill.hero_id == hero_id).scalar_subquery()
        if hero_id is not None
        else select(0).scalar_subquery()
    )

    row = (
        await db.execute(
            select(
                battles_played_sq,
                battles_won_sq,
                arena_played_sq,
                arena_won_sq,
                expeditions_started_sq,
                expeditions_claimed_sq,
                quests_claimed_sq,
                chests_opened_sq,
                referred_total_sq,
                referred_successful_sq,
                campaign_nodes_cleared_sq,
                campaign_total_clears_sq,
                items_equipped_sq,
                skills_upgraded_sq,
            )
        )
    ).one()
    (
        battles_played,
        battles_won,
        arena_played,
        arena_won,
        expeditions_started,
        expeditions_claimed,
        quests_claimed,
        chests_opened,
        referred_total,
        referred_successful,
        campaign_nodes_cleared,
        campaign_total_clears,
        items_equipped,
        skills_upgraded,
    ) = row

    return ProfileStatisticsOut(
        battles=BattleStatsOut(played=battles_played, wins=battles_won, losses=battles_played - battles_won),
        arena=ArenaStatsOut(played=arena_played, wins=arena_won, losses=arena_played - arena_won),
        campaign=CampaignStatsOut(nodes_cleared=campaign_nodes_cleared, total_clears=campaign_total_clears),
        expeditions=ExpeditionStatsOut(started=expeditions_started, claimed=expeditions_claimed),
        quests=QuestStatsOut(claimed=quests_claimed),
        chests=ChestStatsOut(opened=chests_opened),
        referrals=ReferralStatsOut(referral_count=referred_total, successful_referrals=referred_successful),
        hero_activity=HeroActivityStatsOut(items_equipped=items_equipped, skills_upgraded=skills_upgraded),
    )


async def get_my_profile(db: AsyncSession, user: User) -> ProfileOut:
    user_out = await _build_user_me_out(db, user)
    hero = await get_active_hero(db, user)
    statistics = await get_statistics(db, user.id, hero.id if hero else None)
    return ProfileOut(user=user_out, balance=user.balance, statistics=statistics)


async def get_public_profile(db: AsyncSession, user_id: int) -> PublicProfileOut:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")

    hero_row = None
    if user.active_hero_id is not None:
        hero_row = await db.get(UserHero, user.active_hero_id)

    hero_out = None
    if hero_row is not None:
        hero_out = PublicHeroOut(
            name=hero_row.hero_template.name,
            level=hero_row.level,
            race=hero_row.hero_template.race.name,
            character_class=hero_row.hero_template.character_class.name,
        )

    statistics = await get_statistics(db, user.id, hero_row.id if hero_row else None)
    return PublicProfileOut(
        user_id=user.id,
        username=user.username,
        hero=hero_out,
        statistics=PublicStatisticsOut(
            arena_wins=statistics.arena.wins,
            pve_wins=statistics.battles.wins,
            campaign_nodes_cleared=statistics.campaign.nodes_cleared,
            expeditions_claimed=statistics.expeditions.claimed,
            quests_claimed=statistics.quests.claimed,
            chests_opened=statistics.chests.opened,
        ),
    )
