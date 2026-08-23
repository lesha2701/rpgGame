from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.hero_template import HeroTemplate


class UserHero(Base, TimestampMixin):
    """A player's owned hero instance. V1 gives each user at most one (see
    User.active_hero_id + hero_service.create_hero's guard), enforced in the
    service layer rather than a DB constraint, precisely so a later stage
    can allow more than one UserHero per user_id without a migration.

    Deliberately no hp/attack/defense/speed/crit columns: combat stats are
    always derived at read time (services/progression.compute_stats) from
    the class's base + per-level growth, plus — from Stage 4 on — equipped
    item bonuses. A persisted stat column would drift out of sync with
    level/equipment the first time either changes and this function isn't
    also called; deriving it removes that failure mode entirely. Equipment
    (Stage 4) and skills (Stage 3) attach via their own tables referencing
    this hero's id, so neither needs a change here either."""

    __tablename__ = "user_heroes"
    __table_args__ = (
        CheckConstraint("level >= 1 AND level <= 100", name="ck_user_heroes_level_range"),
        CheckConstraint("xp >= 0", name="ck_user_heroes_xp_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    hero_template_id: Mapped[int] = mapped_column(ForeignKey("hero_templates.id"), nullable=False, index=True)

    # Player-chosen at creation, distinct from the shared HeroTemplate.name —
    # nullable only because rows created before this column existed have
    # none; hero_service.hero_to_out falls back to the template name for
    # those. Every hero created going forward always has one (required by
    # schemas.character.CreateHeroRequest).
    name: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # level: 1-100, hard-enforced by the CHECK constraint above as well as
    # services/progression.apply_xp_gain, which never produces a value
    # outside that range. xp is progress toward the *next* level (resets to
    # the carried-over remainder on level-up), not a lifetime total.
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    xp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    hero_template: Mapped["HeroTemplate"] = relationship("HeroTemplate", lazy="joined")
