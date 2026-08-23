from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Rarity
from app.models.mixins import TimestampMixin


class Chest(Base, TimestampMixin):
    """RPG's equivalent of the football app's Pack — structurally adapted,
    not a literal copy: a Chest grants exactly one item per opening.

    Chests used to belong to a fixed equipment Tier (gating both which
    items it could drop and which hero level could open it), removed in a
    later pass: a chest's reward is now capped by the *opening hero's own*
    tier (item_progression.equipment_tier_for_level(hero.level)) — a tier-5
    hero opening ANY chest can receive tier 1-5 items, a tier-3 hero
    opening that same chest only ever receives tier 1-3 items. Chests no
    longer differ by which items they can drop, only by
    price/rarity_probabilities/guaranteed_min_rarity — i.e. how likely a
    *good* item is, not which power band is reachable at all. See
    chest_service.pick_random_item_template.

    Price/probabilities live on this row (and ChestRarityProbability) —
    admin-editable, not hardcoded in chest_service.py — matching the
    football app's Pack/PackRarityProbability: there's no separate
    GameConfig-style table for these, because each chest already IS its own
    configuration."""

    __tablename__ = "chests"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guaranteed_min_rarity: Mapped[Rarity | None] = mapped_column(SAEnum(Rarity, name="item_rarity"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    rarity_probabilities: Mapped[list["ChestRarityProbability"]] = relationship(
        back_populates="chest", cascade="all, delete-orphan", lazy="joined"
    )


class ChestRarityProbability(Base):
    """Ported structurally from the football app's PackRarityProbability —
    same shape (pack_id/rarity/probability -> chest_id/rarity/probability),
    same role: chest_service.roll_rarity reads these as weights, unchanged
    from how pack_service.roll_rarities does it."""

    __tablename__ = "chest_rarity_probabilities"
    __table_args__ = (UniqueConstraint("chest_id", "rarity", name="uq_chest_rarity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chest_id: Mapped[int] = mapped_column(ForeignKey("chests.id", ondelete="CASCADE"), nullable=False, index=True)
    rarity: Mapped[Rarity] = mapped_column(SAEnum(Rarity, name="item_rarity"), nullable=False)
    probability: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)

    chest: Mapped["Chest"] = relationship(back_populates="rarity_probabilities")
