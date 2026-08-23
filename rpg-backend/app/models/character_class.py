from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class CharacterClass(Base, TimestampMixin):
    """Catalog entity — a hero's combat role (Warrior, Archer, ...).
    Independent of Race on purpose (see HeroTemplate). Combat stats live
    here, not on HeroTemplate: every hero of a given class balances
    identically regardless of which named template it came from, so tuning
    a class's power curve is a one-row edit, not N edits across templates."""

    __tablename__ = "character_classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Level-1 baseline.
    base_hp: Mapped[int] = mapped_column(Integer, nullable=False)
    base_attack: Mapped[int] = mapped_column(Integer, nullable=False)
    base_defense: Mapped[int] = mapped_column(Integer, nullable=False)
    base_speed: Mapped[int] = mapped_column(Integer, nullable=False)
    base_crit_chance: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.05)
    base_crit_damage: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=1.5)

    # Flat growth applied per level above 1, automatically — no manual stat
    # allocation in V1 (see services/progression.py). Crit stats don't scale
    # with level in V1; they move via equipment/skills in later stages.
    hp_per_level: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    attack_per_level: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    defense_per_level: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    speed_per_level: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
