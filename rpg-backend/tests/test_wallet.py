"""wallet_service is a near-verbatim port of the football app's — these
tests mirror what such a port should still guarantee: correct balance
math, a CoinTransaction row on every mutation, insufficient-balance
rejection, and (live-verified separately against real Postgres — see the
Stage 5 report) row-lock-serialized concurrent debits."""

import asyncio

import pytest
from tests.factories import get_user_by_telegram_id
from tests.utils import telegram_headers

from app.core.exceptions import InsufficientBalanceError
from app.models.enums import TransactionType
from app.services.wallet_service import credit_coins, debit_coins, lock_user_for_update


async def _register(client, telegram_id, bot_token):
    headers = telegram_headers(telegram_id, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    return headers


async def test_credit_coins_increases_balance_and_logs_transaction(client, db_session, bot_token):
    await _register(client, 7001, bot_token)
    user = await get_user_by_telegram_id(db_session, 7001)
    assert user.balance == 0

    tx = await credit_coins(db_session, user, 500, TransactionType.admin_grant, "test grant")
    await db_session.commit()

    assert user.balance == 500
    assert tx.amount == 500
    assert tx.balance_before == 0
    assert tx.balance_after == 500
    assert tx.type == TransactionType.admin_grant


async def test_debit_coins_decreases_balance_and_logs_transaction(client, db_session, bot_token):
    await _register(client, 7002, bot_token)
    user = await get_user_by_telegram_id(db_session, 7002)
    await credit_coins(db_session, user, 1000, TransactionType.admin_grant)
    await db_session.commit()

    tx = await debit_coins(db_session, user, 300, TransactionType.chest_purchase, "test debit")
    await db_session.commit()

    assert user.balance == 700
    assert tx.amount == -300
    assert tx.balance_before == 1000
    assert tx.balance_after == 700


async def test_debit_more_than_balance_is_rejected(client, db_session, bot_token):
    await _register(client, 7003, bot_token)
    user = await get_user_by_telegram_id(db_session, 7003)
    await credit_coins(db_session, user, 100, TransactionType.admin_grant)
    await db_session.commit()

    with pytest.raises(InsufficientBalanceError):
        await debit_coins(db_session, user, 101, TransactionType.chest_purchase)


async def test_credit_rejects_negative_amount(client, db_session, bot_token):
    await _register(client, 7004, bot_token)
    user = await get_user_by_telegram_id(db_session, 7004)
    with pytest.raises(ValueError):
        await credit_coins(db_session, user, -1, TransactionType.admin_grant)


async def test_debit_rejects_negative_amount(client, db_session, bot_token):
    await _register(client, 7005, bot_token)
    user = await get_user_by_telegram_id(db_session, 7005)
    with pytest.raises(ValueError):
        await debit_coins(db_session, user, -1, TransactionType.chest_purchase)


async def test_balance_never_goes_negative_at_the_db_level(client, db_session, bot_token):
    """Defense in depth: the CHECK constraint on users.balance, not just
    the application-level guard in debit_coins."""
    await _register(client, 7006, bot_token)
    user = await get_user_by_telegram_id(db_session, 7006)
    user.balance = -1
    db_session.add(user)
    with pytest.raises(Exception):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.skip(
    reason=(
        "Same documented SQLite limitation as the Stage 3/4 concurrency "
        "tests — no real row-level locking on a shared StaticPool "
        "connection. Kept as executable documentation; the real "
        "enforcement (two concurrent debits, balance for only one) was "
        "verified live against rpg-postgres — see the Stage 5 report."
    )
)
async def test_concurrent_debits_never_overdraw_the_balance(client, db_session, bot_token):
    from tests.conftest import TestSessionLocal

    await _register(client, 7007, bot_token)
    user = await get_user_by_telegram_id(db_session, 7007)
    await credit_coins(db_session, user, 100, TransactionType.admin_grant)
    await db_session.commit()
    user_id = user.id

    async def attempt(amount: int) -> str:
        async with TestSessionLocal() as session:
            try:
                locked = await lock_user_for_update(session, user_id)
                await debit_coins(session, locked, amount, TransactionType.chest_purchase)
                await session.commit()
                return "ok"
            except Exception as exc:
                return type(exc).__name__

    results = await asyncio.gather(attempt(100), attempt(100))
    assert sorted(results) == ["InsufficientBalanceError", "ok"]

    async with TestSessionLocal() as session:
        refreshed = await get_user_by_telegram_id(session, 7007)
        assert refreshed.balance == 0
