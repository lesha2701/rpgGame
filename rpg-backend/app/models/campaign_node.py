from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import CampaignNodeType
from app.models.mixins import TimestampMixin


class CampaignNode(Base, TimestampMixin):
    """One encounter on the campaign map. `enemy_template_id` is the single
    opponent for battle/elite/boss nodes (V1 has no multi-enemy nodes); it
    is nullable only so the schema doesn't need a migration when
    story_event/treasure/merchant/rest node types (reserved in
    CampaignNodeType, not implemented in Stage 13) eventually need a node
    with no enemy.

    `depth` is the node's distance (in steps) from its region's entry
    point along the main progression axis — used by the frontend to lay
    branches out left-to-right/top-to-bottom; CampaignNodeEdge is what
    actually determines availability and traversal, depth is presentation
    only. `level` is a *recommended* level shown to the player, never a
    hard gate (Stage 13 spec §1/§2) — nothing in campaign_service checks
    hero.level against it."""

    __tablename__ = "campaign_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("campaign_regions.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    node_type: Mapped[CampaignNodeType] = mapped_column(SAEnum(CampaignNodeType, name="campaign_node_type"), nullable=False)
    enemy_template_id: Mapped[int | None] = mapped_column(ForeignKey("enemy_templates.id"), nullable=True, index=True)

    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
