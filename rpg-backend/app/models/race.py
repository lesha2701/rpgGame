from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class Race(Base, TimestampMixin):
    """Catalog entity — a hero's lineage (Human, Orc, ...). Independent of
    CharacterClass on purpose (see HeroTemplate): content can grow without a
    schema change, and nothing here contributes to combat stats in V1 — race
    is flavor + the future second axis for visual-stage art (Stage 12)."""

    __tablename__ = "races"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
