from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.character_class import CharacterClass
    from app.models.race import Race


class HeroTemplate(Base, TimestampMixin):
    """A specific recruitable hero (e.g. "Aldric", a Human Warrior) — the
    catalog a player picks from in POST /heroes. Combines a Race and a
    CharacterClass by reference; deliberately NOT every race x class
    combination is pre-generated (see rpg-backend/app/seed.py) — Race and
    CharacterClass stay independent catalogs that new templates can mix and
    match without a schema change."""

    __tablename__ = "hero_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id"), nullable=False, index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("character_classes.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Level-1 default portrait. The full 10-stage art chain (Stage 12) will
    # live in a separate table keyed by (class, stage) or (template, stage)
    # — adding it needs no change here or on UserHero.
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    race: Mapped["Race"] = relationship("Race", lazy="joined")
    character_class: Mapped["CharacterClass"] = relationship("CharacterClass", lazy="joined")
