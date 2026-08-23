from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CampaignNodeEdge(Base):
    """One directed edge in the campaign graph: completing `from_node_id`
    is one of the ways `to_node_id` becomes available. A node can have
    multiple incoming edges (a merge point — available once ANY source is
    completed) and multiple outgoing edges (a branch point) — see
    campaign_service.py's availability computation, which is a uniform
    OR-rule over exactly this table plus UserCampaignNodeClear, no special
    casing for branch vs. merge. A node with zero incoming edges (a
    region's entry point) is available unconditionally."""

    __tablename__ = "campaign_node_edges"
    __table_args__ = (
        UniqueConstraint("from_node_id", "to_node_id", name="uq_campaign_node_edges_pair"),
        CheckConstraint("from_node_id != to_node_id", name="ck_campaign_node_edges_no_self_loop"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_node_id: Mapped[int] = mapped_column(ForeignKey("campaign_nodes.id"), nullable=False, index=True)
    to_node_id: Mapped[int] = mapped_column(ForeignKey("campaign_nodes.id"), nullable=False, index=True)
