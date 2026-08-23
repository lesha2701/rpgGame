from sqlalchemy import JSON, Boolean, CheckConstraint, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class EnemyTemplate(Base, TimestampMixin):
    """PvE opponent catalog — plain stat block, no skills (enemies always
    Basic Attack in Stage 6, see battle_engine.py's module docstring for
    why: no EnemyTemplateSkill join table needed). Unlike ItemTemplate/
    Chest, stats here are NOT derived from a tier formula — an enemy's
    numbers are authored directly, same as the football app's bots having
    hand-set stat blocks for narrative/balance control (see the Stage 6
    design doc's comparison of dynamic vs. authored PvE difficulty).

    `level` doubles as the required hero level to challenge this enemy
    (battle_service checks hero.level >= enemy.level) — no separate
    required_hero_level column, so there's only one number to keep in sync
    when rebalancing."""

    __tablename__ = "enemy_templates"
    __table_args__ = (
        CheckConstraint("level >= 1", name="ck_enemy_templates_level_positive"),
        CheckConstraint("hp > 0", name="ck_enemy_templates_hp_positive"),
        CheckConstraint("reward_xp >= 0", name="ck_enemy_templates_reward_xp_non_negative"),
        CheckConstraint("reward_coins >= 0", name="ck_enemy_templates_reward_coins_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    hp: Mapped[int] = mapped_column(Integer, nullable=False)
    attack: Mapped[int] = mapped_column(Integer, nullable=False)
    defense: Mapped[int] = mapped_column(Integer, nullable=False)
    speed: Mapped[int] = mapped_column(Integer, nullable=False)
    crit_chance: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.05)
    crit_damage: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=1.5)

    reward_xp: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_coins: Mapped[int] = mapped_column(Integer, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Stage 13: marks an enemy eligible for BossPhase rows (checked once
    # per round by campaign_battle_service against current HP%) and for
    # the Boss campaign-node type. False (a plain enemy) for every
    # pre-Stage-13 row.
    is_boss: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    # Stage 13: mirrors battle_engine.CombatantStats.stun_immune — lets a
    # boss ignore vanilla Stun (still counterable by an
    # SkillDefinition.is_interrupt-flagged skill). False for every
    # pre-Stage-13 row.
    stun_immune: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    # Stage 13: ordered list of EnemyAbility.code strings this enemy
    # cycles through round-by-round (falling back to Basic Attack if the
    # next ability in the pattern is on cooldown — same tolerance the hero
    # AI's _pick_ready_skill and Arena's cooldown-recheck already use).
    # None/empty for every pre-Stage-13 row and every enemy that hasn't
    # been given a campaign moveset yet — such an enemy always Basic
    # Attacks, identical to today's Stage 6 behavior.
    behavior_pattern: Mapped[list | None] = mapped_column(JSON, nullable=True)
