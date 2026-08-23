from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import TransactionType
from app.models.mixins import TimestampMixin


class CoinTransaction(Base, TimestampMixin):
    """One row per balance mutation — the audit trail wallet_service.py
    writes alongside every credit_coins/debit_coins call. Ported near-
    verbatim from the football app's app/models/transaction.py (same
    columns, same balance_before/after snapshot approach); TransactionType's
    values are RPG-specific."""

    __tablename__ = "coin_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Signed: positive for a credit, negative for a debit — balance_after -
    # balance_before always equals this exactly.
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_before: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[TransactionType] = mapped_column(SAEnum(TransactionType, name="transaction_type"), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    related_object_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    related_object_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
