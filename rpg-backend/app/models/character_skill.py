from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.skill_definition import SkillDefinition


class CharacterSkill(Base, TimestampMixin):
    """One hero's progress on one skill. Rows are created lazily — a skill
    the hero hasn't invested in yet simply has no row (see
    skill_service.upgrade_skill), rather than existing at some "level 0".
    Level range is 1-10 for exactly that reason: 0 is "not learned",
    represented by the row's absence, not a storable level."""

    __tablename__ = "character_skills"
    __table_args__ = (
        UniqueConstraint("hero_id", "skill_definition_id", name="uq_character_skills_hero_skill"),
        CheckConstraint("level >= 1 AND level <= 10", name="ck_character_skills_level_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hero_id: Mapped[int] = mapped_column(ForeignKey("user_heroes.id"), nullable=False, index=True)
    skill_definition_id: Mapped[int] = mapped_column(ForeignKey("skill_definitions.id"), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    skill_definition: Mapped["SkillDefinition"] = relationship("SkillDefinition", lazy="joined")
