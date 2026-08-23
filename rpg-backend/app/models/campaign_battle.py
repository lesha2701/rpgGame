from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, JSON, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import BattleResult, CampaignBattleStatus


class CampaignBattle(Base):
    """One interactive PvE campaign fight — Variant C from the Stage 13
    design report: a stateful, row-locked, resumable session structurally
    parallel to ArenaMatch, but single-player (no opponent to sweep for,
    so no round_deadline_at/AFK handling — a player can sit on a `running`
    CampaignBattle indefinitely with no consequence). On finish, exactly
    one ordinary immutable Battle row is written (unchanged shape, for
    history-screen compatibility) — this table is never itself read as
    battle history; Battle stays the single source for that.

    `state` (JSON) holds: the hero's frozen CombatantState + skills
    snapshot (copied once at creation, same as Arena), the enemy's
    CombatantState + its EnemyAbility catalog + current position in
    behavior_pattern + active boss phase index, and the queued enemy
    intent for the upcoming round (ability code + precomputed damage
    range, shown to the player before they act — see
    campaign_battle_service.py for the exact shape). No pending_action
    field like ArenaMatch: the hero's action and the round resolution
    happen in the same request (there's no second player to wait on), so
    there's nothing to persist as "pending" between requests.

    A hero can have at most one `running` CampaignBattle at a time
    (enforced below, same partial-unique-index pattern as ArenaMatch) —
    not a hard architectural requirement, but prevents two browser tabs
    from resolving the same node concurrently and double-granting reward/
    node-clear."""

    __tablename__ = "campaign_battles"
    __table_args__ = (
        CheckConstraint("current_round >= 1", name="ck_campaign_battles_round_positive"),
        CheckConstraint("reward_xp >= 0", name="ck_campaign_battles_reward_xp_non_negative"),
        CheckConstraint("reward_coins >= 0", name="ck_campaign_battles_reward_coins_non_negative"),
        Index(
            "uq_campaign_battles_hero_running",
            "hero_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
            sqlite_where=text("status = 'running'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    hero_id: Mapped[int] = mapped_column(ForeignKey("user_heroes.id"), nullable=False, index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("campaign_nodes.id"), nullable=False, index=True)
    enemy_template_id: Mapped[int] = mapped_column(ForeignKey("enemy_templates.id"), nullable=False, index=True)

    status: Mapped[CampaignBattleStatus] = mapped_column(
        SAEnum(CampaignBattleStatus, name="campaign_battle_status"), nullable=False
    )
    current_round: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    state: Mapped[dict] = mapped_column(JSON, nullable=False)
    log: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    result: Mapped[Optional[BattleResult]] = mapped_column(
        SAEnum(BattleResult, name="battle_result"), nullable=True
    )
    is_first_clear: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reward_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reward_coins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
