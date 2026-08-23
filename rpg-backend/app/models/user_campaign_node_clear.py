from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserCampaignNodeClear(Base):
    """The ONE stored fact campaign progress is built from — everything
    else (`completed`/`available`/`locked`/`current`/focus_node_id) is
    computed at read time from this table plus CampaignNodeEdge (Stage 13
    spec: "derive, don't store", same call as ExpeditionStatus/
    ArenaMatchStatus already make elsewhere in this codebase). A node is
    `completed` iff a row exists here for (user, node); `clear_count`
    distinguishes a First Clear (reward = 100%, granted when the row is
    first inserted) from every Repeat Clear (reward = a fixed fraction,
    see campaign_battle_service.REPEAT_CLEAR_REWARD_FRACTION) without
    needing a second table."""

    __tablename__ = "user_campaign_node_clears"
    __table_args__ = (UniqueConstraint("user_id", "node_id", name="uq_user_campaign_node_clears_user_node"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("campaign_nodes.id"), nullable=False, index=True)

    first_cleared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_cleared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    clear_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
