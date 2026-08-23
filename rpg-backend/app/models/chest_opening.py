from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.database import Base


class ChestOpening(Base):
    """One row per chest opened — the idempotency guarantee (like the
    football app's PackOpening) comes from the DB unique constraint below,
    not from the X-Idempotency-Key header alone. One chest grants exactly
    one item in V1 (no PackOpeningCard-style join table needed —
    reward_user_item_id points at the single UserItem created)."""

    __tablename__ = "chest_openings"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_chest_opening_idem"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    chest_id: Mapped[int] = mapped_column(ForeignKey("chests.id"), nullable=False, index=True)
    reward_user_item_id: Mapped[int] = mapped_column(ForeignKey("user_items.id"), nullable=False)
    price_paid: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
