from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class CampaignRegion(Base, TimestampMixin):
    """One visually-themed chapter of the level-1-to-~100 campaign (Stage
    13 spec §11) — e.g. "Тёмный лес" (levels 1-10), through to a final
    endgame zone. Purely presentational/grouping data; a node's own `depth`
    plus CampaignNodeEdge is what actually orders progression — sort_order
    here only orders regions in the region list/map, it isn't consulted by
    the availability/focus_node_id computation in campaign_service.py."""

    __tablename__ = "campaign_regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
