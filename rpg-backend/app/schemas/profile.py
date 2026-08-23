from pydantic import BaseModel

from app.schemas.auth import UserMeOut


class BattleStatsOut(BaseModel):
    played: int
    wins: int
    losses: int


class ArenaStatsOut(BaseModel):
    played: int
    wins: int
    losses: int


class ExpeditionStatsOut(BaseModel):
    started: int
    claimed: int


class QuestStatsOut(BaseModel):
    claimed: int


class ChestStatsOut(BaseModel):
    opened: int


class ReferralStatsOut(BaseModel):
    # Everyone who registered with this user's code (raw), vs. how many of
    # them triggered the reward (see referral_service.py) — two genuinely
    # different derived numbers, not one duplicated under two names.
    referral_count: int
    successful_referrals: int


class CampaignStatsOut(BaseModel):
    # nodes_cleared: distinct nodes ever cleared (first-clear count).
    # total_clears: sum of every clear_count, i.e. first clears + repeats.
    nodes_cleared: int
    total_clears: int


class HeroActivityStatsOut(BaseModel):
    items_equipped: int
    skills_upgraded: int


class ProfileStatisticsOut(BaseModel):
    battles: BattleStatsOut
    arena: ArenaStatsOut
    campaign: CampaignStatsOut
    expeditions: ExpeditionStatsOut
    quests: QuestStatsOut
    chests: ChestStatsOut
    referrals: ReferralStatsOut
    hero_activity: HeroActivityStatsOut


class ProfileOut(BaseModel):
    # Reused wholesale (id/telegram_id/username/active_hero/referral_code/
    # referral_count already exist there — no reason to re-declare a
    # near-duplicate "user" block for the private profile).
    user: UserMeOut
    balance: int
    statistics: ProfileStatisticsOut


class PublicHeroOut(BaseModel):
    name: str
    level: int
    race: str
    character_class: str


class PublicStatisticsOut(BaseModel):
    """Deliberately a narrower, flat set — not ProfileStatisticsOut reused
    wholesale — matching exactly what Stage 11's brief allows to be public:
    wins only (not played/losses), no referral data, no balance."""

    arena_wins: int
    pve_wins: int
    campaign_nodes_cleared: int
    expeditions_claimed: int
    quests_claimed: int
    chests_opened: int


class PublicProfileOut(BaseModel):
    # user.id doubles as the public lookup key — already de facto quasi-
    # public via Arena's own challenge flow (POST /arena/matches takes an
    # opponent_user_id), so this isn't a new kind of exposure; no
    # telegram_id, no balance, no referral data.
    user_id: int
    username: str | None
    hero: PublicHeroOut | None
    statistics: PublicStatisticsOut
