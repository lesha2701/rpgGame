from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import EquipmentSlot
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.item_template import ItemTemplate


class UserItem(Base, TimestampMixin):
    """A player's owned item instance. Owned by a user (owner_user_id, the
    inventory), optionally equipped onto one hero (equipped_hero_id,
    nullable — None means "sitting in inventory"). `slot` is denormalized
    from item_template.slot at creation time (an item's slot never changes,
    so this can't drift) specifically so the DB itself can enforce "at most
    one equipped item per slot per hero" via the partial unique index
    below, rather than relying only on application-level checks."""

    __tablename__ = "user_items"
    __table_args__ = (
        Index(
            "uq_user_items_one_per_slot_per_hero",
            "equipped_hero_id",
            "slot",
            unique=True,
            postgresql_where=text("equipped_hero_id IS NOT NULL"),
            sqlite_where=text("equipped_hero_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    item_template_id: Mapped[int] = mapped_column(ForeignKey("item_templates.id"), nullable=False, index=True)
    slot: Mapped[EquipmentSlot] = mapped_column(SAEnum(EquipmentSlot, name="equipment_slot"), nullable=False)
    equipped_hero_id: Mapped[int | None] = mapped_column(ForeignKey("user_heroes.id"), nullable=True, index=True)

    item_template: Mapped["ItemTemplate"] = relationship("ItemTemplate", lazy="joined")
