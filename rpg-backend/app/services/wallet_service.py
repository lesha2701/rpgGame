"""Ported near-verbatim from the football app's app/services/wallet_service.py
— lock_user_for_update, credit_coins, and debit_coins are functionally
identical (same locking reasoning, same balance_before/after snapshot on
every CoinTransaction, same InsufficientBalanceError guard). Only the
TransactionType values differ (RPG-scoped, see models/enums.py).

lock_user_for_update also replaces hero_service.py's own copy of the same
function (Stage 1-4 defined it there since coins didn't exist yet) — this
is now the one canonical implementation, matching where the football app
keeps it."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientBalanceError
from app.models.enums import TransactionType
from app.models.transaction import CoinTransaction
from app.models.user import User


async def lock_user_for_update(db: AsyncSession, user_id: int) -> User:
    """SELECT ... FOR UPDATE + populate_existing: the user row may already
    be in the session's identity map from get_current_user, so without
    populate_existing a locked-but-stale copy could be read (the FOR UPDATE
    lock would still serialize correctly at the SQL level, but the caller's
    check-then-write would read outdated values, making the lock pointless).
    RPG's User has no lazy="joined" relationships (Stage 1's deliberate
    choice — see User's docstring history), so unlike the football app's
    equivalent this doesn't need with_for_update(of=User) scoping; a plain
    with_for_update() is unambiguous here."""
    result = await db.execute(
        select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def credit_coins(
    db: AsyncSession,
    user: User,
    amount: int,
    tx_type: TransactionType,
    description: str = "",
    related_object_type: Optional[str] = None,
    related_object_id: Optional[int] = None,
) -> CoinTransaction:
    if amount < 0:
        raise ValueError("credit_coins amount must be >= 0")
    balance_before = user.balance
    user.balance = balance_before + amount
    tx = CoinTransaction(
        user_id=user.id,
        amount=amount,
        balance_before=balance_before,
        balance_after=user.balance,
        type=tx_type,
        description=description,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
    )
    db.add(tx)
    db.add(user)
    return tx


async def debit_coins(
    db: AsyncSession,
    user: User,
    amount: int,
    tx_type: TransactionType,
    description: str = "",
    related_object_type: Optional[str] = None,
    related_object_id: Optional[int] = None,
) -> CoinTransaction:
    if amount < 0:
        raise ValueError("debit_coins amount must be >= 0")
    if user.balance < amount:
        raise InsufficientBalanceError(
            "Not enough coins",
            details={"balance": user.balance, "required": amount},
        )
    balance_before = user.balance
    user.balance = balance_before - amount
    tx = CoinTransaction(
        user_id=user.id,
        amount=-amount,
        balance_before=balance_before,
        balance_after=user.balance,
        type=tx_type,
        description=description,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
    )
    db.add(tx)
    db.add(user)
    return tx
