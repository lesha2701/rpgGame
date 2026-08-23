from sqlalchemy import Boolean, CheckConstraint, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import SkillType
from app.models.mixins import TimestampMixin


class SkillDefinition(Base, TimestampMixin):
    """A skill belongs to a CharacterClass, not to any one UserHero — every
    hero of a class shares the same 3 skill definitions (see seed data);
    CharacterSkill is what tracks one hero's own progress on one of them.

    Carries the data a future battle engine (Stage 8/9) will need, but does
    not itself compute damage/healing/buffs/DoT/stun/cooldowns — skill_type,
    base_power, power_per_skill_level and cooldown_turns are inert data
    here."""

    __tablename__ = "skill_definitions"
    __table_args__ = (
        UniqueConstraint("class_id", "code", name="uq_skill_definitions_class_code"),
        CheckConstraint("required_hero_level >= 1 AND required_hero_level <= 100", name="ck_skill_definitions_required_level_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("character_classes.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill_type: Mapped[SkillType] = mapped_column(SAEnum(SkillType, name="skill_type"), nullable=False)

    # Future battle-engine inputs — magnitude of the skill's effect at skill
    # level 1, and how much it grows per additional skill level (1-10).
    # What "power" means depends on skill_type (damage dealt, HP healed,
    # shield absorbed, DoT per tick, buff/debuff magnitude...) — that
    # interpretation belongs to the battle engine, not here.
    base_power: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    power_per_skill_level: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    cooldown_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Unlock requirement: the hero must be at least this level before the
    # skill can be learned at all (see services/skill_service.upgrade_skill).
    required_hero_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Stage 13: which stat a buff/debuff-type skill modifies — mirrors
    # battle_engine.BattleSkill.buff_stat exactly, "attack" reproducing
    # every skill that existed before this column did. Only meaningful
    # when skill_type is buff/debuff.
    buff_stat: Mapped[str] = mapped_column(String(16), nullable=False, default="attack", server_default="attack")
    # Stage 13: lets this skill cancel a queued campaign-enemy intent even
    # through stun_immune (see campaign_battle_service.py). Unused by
    # PvE/Arena. False for every pre-Stage-13 skill.
    is_interrupt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
