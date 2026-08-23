from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BossPhase(Base):
    """One HP-threshold phase of an EnemyTemplate with is_boss=True.
    campaign_battle_service checks the boss's current HP% against every
    phase's hp_threshold_pct once per round (highest threshold whose value
    is still >= current HP% wins) and applies that phase's overrides for
    the rest of the fight until the next (lower) threshold is crossed.

    `behavior_pattern` overrides EnemyTemplate.behavior_pattern for the
    duration of this phase when set (None = keep whatever pattern was
    already active — lets a phase change stats/text without also having
    to repeat an unchanged moveset). attack_multiplier/defense_multiplier
    apply on top of the boss's base stats, not stacking across phases —
    each phase's multiplier is absolute, not cumulative.

    `transition_text` is shown exactly once, as a combat log entry, the
    first round this phase becomes active (Stage 13 spec §9: a phase
    change must be visibly noticeable, never silent)."""

    __tablename__ = "boss_phases"
    __table_args__ = (
        UniqueConstraint("enemy_template_id", "phase_order", name="uq_boss_phases_template_order"),
        CheckConstraint("hp_threshold_pct >= 0 AND hp_threshold_pct <= 100", name="ck_boss_phases_threshold_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    enemy_template_id: Mapped[int] = mapped_column(ForeignKey("enemy_templates.id"), nullable=False, index=True)
    phase_order: Mapped[int] = mapped_column(Integer, nullable=False)

    # Phase is active once current_hp_pct <= this value (phase_order=1
    # conventionally uses 100 — active from the start of the fight).
    hp_threshold_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    behavior_pattern: Mapped[list | None] = mapped_column(JSON, nullable=True)
    attack_multiplier: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=1.0)
    defense_multiplier: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=1.0)
    unlock_ability_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transition_text: Mapped[str | None] = mapped_column(Text, nullable=True)
