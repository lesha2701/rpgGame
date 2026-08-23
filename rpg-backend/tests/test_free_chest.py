import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from tests.factories import create_chest, create_hero_template, create_item_template, get_user_by_telegram_id
from tests.utils import telegram_headers

from app.models.chest import Chest
from app.models.chest_opening import ChestOpening
from app.models.enums import EquipmentSlot, Rarity, TransactionType
from app.models.user import User
from app.services.wallet_service import credit_coins


async def _make_hero(client, db_session, telegram_id, bot_token) -> tuple[int, dict]:
    template = await create_hero_template(db_session, name=f"Hero{telegram_id}")
    await db_session.commit()
    headers = telegram_headers(telegram_id, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id, "name": "Герой"})
    assert resp.status_code == 201
    return resp.json()["id"], headers


async def _seed_free_chest(db_session) -> Chest:
    chest = await create_chest(db_session, price=0, slug="free-chest")
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()
    return chest


async def _get_free_chest(db_session) -> Chest:
    result = await db_session.execute(select(Chest).where(Chest.slug == "free-chest"))
    return result.unique().scalar_one()


async def _last_free_chest_opening(db_session, user_id: int, chest_id: int) -> ChestOpening:
    result = await db_session.execute(
        select(ChestOpening)
        .where(ChestOpening.user_id == user_id, ChestOpening.chest_id == chest_id)
        .order_by(ChestOpening.id.desc())
        .limit(1)
    )
    return result.scalar_one()


async def _rewind_last_opening(db_session, user_id: int, chest_id: int, hours_ago: float) -> None:
    opening = await _last_free_chest_opening(db_session, user_id, chest_id)
    opening.created_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    db_session.add(opening)
    await db_session.commit()


# --- availability / status --------------------------------------------------

async def test_free_chest_is_available_before_any_claim(client, db_session, bot_token):
    await _seed_free_chest(db_session)
    _hero_id, headers = await _make_hero(client, db_session, 31001, bot_token)

    resp = await client.get("/api/v1/chests/free", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_available"] is True
    assert body["next_available_at"] is None
    assert body["chest"]["price"] == 0
    assert body["chest"]["slug"] == "free-chest"


async def test_free_chest_price_is_zero(client, db_session, bot_token):
    chest = await _seed_free_chest(db_session)
    assert chest.price == 0


# --- claim / cooldown --------------------------------------------------------

async def test_first_claim_succeeds_and_grants_an_item(client, db_session, bot_token):
    await _seed_free_chest(db_session)
    _hero_id, headers = await _make_hero(client, db_session, 31002, bot_token)

    resp = await client.post("/api/v1/chests/free/claim", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["reward"]["item_id"] is not None
    assert body["balance"] == 0  # free — nothing was ever debited

    inventory = await client.get("/api/v1/heroes/me/inventory", headers=headers)
    assert any(i["id"] == body["reward"]["item_id"] for i in inventory.json())


async def test_second_claim_before_cooldown_is_409(client, db_session, bot_token):
    await _seed_free_chest(db_session)
    _hero_id, headers = await _make_hero(client, db_session, 31003, bot_token)

    first = await client.post("/api/v1/chests/free/claim", headers=headers)
    assert first.status_code == 200

    second = await client.post("/api/v1/chests/free/claim", headers=headers)
    assert second.status_code == 409
    assert "next_available_at" in second.json()["error"]["details"]

    status = await client.get("/api/v1/chests/free", headers=headers)
    assert status.json()["is_available"] is False
    assert status.json()["next_available_at"] is not None


async def test_claim_succeeds_again_after_the_cooldown_elapses(client, db_session, bot_token):
    await _seed_free_chest(db_session)
    _hero_id, headers = await _make_hero(client, db_session, 31004, bot_token)

    first = await client.post("/api/v1/chests/free/claim", headers=headers)
    assert first.status_code == 200

    user = await get_user_by_telegram_id(db_session, 31004)
    free_chest = await _get_free_chest(db_session)
    await _rewind_last_opening(db_session, user.id, free_chest.id, hours_ago=25)

    second = await client.post("/api/v1/chests/free/claim", headers=headers)
    assert second.status_code == 200


async def test_next_available_at_is_24_hours_after_the_last_opening(client, db_session, bot_token):
    await _seed_free_chest(db_session)
    _hero_id, headers = await _make_hero(client, db_session, 31005, bot_token)

    claimed = await client.post("/api/v1/chests/free/claim", headers=headers)
    assert claimed.status_code == 200

    status = await client.get("/api/v1/chests/free", headers=headers)
    next_at = datetime.fromisoformat(status.json()["next_available_at"])

    user = await get_user_by_telegram_id(db_session, 31005)
    free_chest = await _get_free_chest(db_session)
    opening = await _last_free_chest_opening(db_session, user.id, free_chest.id)

    expected = opening.created_at.replace(tzinfo=timezone.utc) + timedelta(hours=24)
    assert abs((next_at - expected).total_seconds()) < 2


async def test_ordinary_paid_chests_are_unaffected_by_free_chest_cooldown(client, db_session, bot_token):
    await _seed_free_chest(db_session)
    paid_chest = await create_chest(db_session, price=100, slug="paid-chest-unaffected")
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 31006, bot_token)

    user = await get_user_by_telegram_id(db_session, 31006)
    await credit_coins(db_session, user, 1000, TransactionType.admin_grant)
    await db_session.commit()

    await client.post("/api/v1/chests/free/claim", headers=headers)  # uses up the free chest

    paid_resp = await client.post(f"/api/v1/chests/{paid_chest.id}/open", headers=headers, json={})
    assert paid_resp.status_code == 200  # unaffected by the free chest's cooldown

    status = await client.get("/api/v1/chests/free", headers=headers)
    assert status.json()["is_available"] is False  # still on cooldown, unaffected by the paid open


async def test_claiming_without_a_hero_is_404(client, db_session, bot_token):
    await _seed_free_chest(db_session)
    headers = telegram_headers(31007, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/chests/free/claim", headers=headers)
    assert resp.status_code == 404


async def test_free_chest_debits_zero_coins(client, db_session, bot_token):
    await _seed_free_chest(db_session)
    _hero_id, headers = await _make_hero(client, db_session, 31008, bot_token)

    resp = await client.post("/api/v1/chests/free/claim", headers=headers)
    assert resp.status_code == 200
    wallet = await client.get("/api/v1/economy", headers=headers)
    assert wallet.json()["coins"] == 0


async def test_no_free_chest_available_at_column_on_user(client, db_session, bot_token):
    """Documents the architectural decision directly: cooldown is derived
    from ChestOpening, not a stored column on User."""
    assert not hasattr(User, "free_chest_available_at")


# --- concurrency: verified live against rpg-postgres, skipped here -----------

@pytest.mark.skip(
    reason=(
        "Same documented SQLite limitation as every other Stage 3-9 "
        "concurrency test — no real row-level locking on a shared "
        "StaticPool connection. Kept as executable documentation; the real "
        "enforcement was verified live against rpg-postgres — see the "
        "Stage 10 report."
    )
)
async def test_concurrent_free_chest_claims_yield_exactly_one_success(client, db_session, bot_token):
    from tests.conftest import TestSessionLocal

    await _seed_free_chest(db_session)
    _hero_id, headers = await _make_hero(client, db_session, 31009, bot_token)

    user = await get_user_by_telegram_id(db_session, 31009)
    user_id = user.id

    async def attempt(label: str) -> str:
        async with TestSessionLocal() as session:
            from app.services.free_chest_service import claim
            from app.services.hero_service import get_active_hero

            u = await session.get(User, user_id)
            hero = await get_active_hero(session, u)
            try:
                await claim(session, u, hero)
                return f"{label} ok"
            except Exception as exc:
                return f"{label} {type(exc).__name__}"

    results = await asyncio.gather(attempt("A"), attempt("B"))
    assert sorted(results) == ["A ConflictError", "B ok"] or sorted(results) == ["A ok", "B ConflictError"]

    async with TestSessionLocal() as session:
        free_chest = await _get_free_chest(session)
        openings = (
            await session.execute(
                select(ChestOpening).where(ChestOpening.user_id == user_id, ChestOpening.chest_id == free_chest.id)
            )
        ).scalars().all()
        assert len(openings) == 1
