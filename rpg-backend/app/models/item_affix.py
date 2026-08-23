from sqlalchemy import Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import ItemStatType
from app.models.mixins import TimestampMixin


class ItemAffix(Base, TimestampMixin):
    """One secondary-stat bonus on an ItemTemplate. Deterministic and
    template-level (not randomly rolled per instance) — Stage 4 has no
    chest/drop system yet, so every UserItem of a given template shares
    the exact same affixes. Magnitude is not stored: it's computed from
    the template's tier at read time (item_progression.affix_power), same
    as the primary stat allocation."""

    __tablename__ = "item_affixes"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_template_id: Mapped[int] = mapped_column(ForeignKey("item_templates.id"), nullable=False, index=True)
    stat_type: Mapped[ItemStatType] = mapped_column(SAEnum(ItemStatType, name="item_stat_type"), nullable=False)
