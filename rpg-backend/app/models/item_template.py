from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Enum as SAEnum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import EquipmentSlot, Rarity
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.item_affix import ItemAffix


class ItemTemplate(Base, TimestampMixin):
    """Catalog entry: what an item IS (slot/tier/rarity/name/art), never how
    many stat points it grants — those are computed at read time from
    (slot, tier, rarity) by services/item_progression.py, the same
    derive-don't-store principle as CharacterClass/HeroTemplate stats.
    required_hero_level is likewise derived from tier
    (item_progression.required_level_for_tier), not a stored column — tier
    is the single source of truth for both."""

    __tablename__ = "item_templates"
    __table_args__ = (CheckConstraint("tier >= 1 AND tier <= 10", name="ck_item_templates_tier_range"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    slot: Mapped[EquipmentSlot] = mapped_column(SAEnum(EquipmentSlot, name="equipment_slot"), nullable=False, index=True)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    rarity: Mapped[Rarity] = mapped_column(SAEnum(Rarity, name="item_rarity"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Rarity determines how many of these a template should have (Common=0,
    # Rare=1, Epic=2, Legendary=3 — see item_progression.RARITY_AFFIX_COUNT)
    # — enforced at seed/creation time, not a DB constraint (a per-row COUNT
    # check isn't expressible as a plain CHECK constraint).
    affixes: Mapped[list["ItemAffix"]] = relationship("ItemAffix", lazy="joined", order_by="ItemAffix.id")
