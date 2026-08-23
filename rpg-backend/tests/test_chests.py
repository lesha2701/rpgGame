import asyncio

import pytest
from tests.factories import (
    create_chest,
    create_hero_template,
    create_item_template,
    get_user_by_telegram_id,
    set_balance,
    set_hero_level,
)
from tests.utils import telegram_headers

from app.models.enums import EquipmentSlot, Rarity, TransactionType
from app.services.chest_service import open_chest, pick_random_item_template, roll_rarity
from app.services.item_progression import MAX_TIER, assert_tier_dominance_holds, item_power
from app.services.wallet_service import credit_coins


async def _make_hero(client, db_session, telegram_id, bot_token, level: int = 1):
    template = await create_hero_template(db_session, name=f"Герой{telegram_id}")
    await db_session.commit()
    headers = telegram_headers(telegram_id, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id})
    assert resp.status_code == 201
    hero_id = resp.json()["id"]
    if level != 1:
        await set_hero_level(db_session, hero_id, level)
        await db_session.commit()
    return hero_id, headers


async def _fund(db_session, telegram_id, amount):
    user = await get_user_by_telegram_id(db_session, telegram_id)
    await credit_coins(db_session, user, amount, TransactionType.admin_grant)
    await db_session.commit()


# --- no more level gate: any hero can open any chest, loot is capped by their own tier --

async def test_low_level_hero_can_open_any_chest_but_never_gets_above_their_own_tier(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 8001, bot_token, level=1)  # tier 1
    await _fund(db_session, 8001, 100_000)
    chest = await create_chest(db_session, price=100)
    for tier in range(1, 6):
        await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=tier, rarity=Rarity.common)
    await db_session.commit()

    for _ in range(15):
        resp = await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers, json={})
        assert resp.status_code == 200  # no hero-level gate to open a chest anymore
        assert resp.json()["reward"]["tier"] == 1  # but loot never exceeds the hero's own tier


async def test_chest_list_no_longer_reports_tier_or_availability_fields(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 8003, bot_token, level=1)
    await create_chest(db_session, price=1000, slug="no-tier-chest")
    await db_session.commit()

    resp = await client.get("/api/v1/chests", headers=headers)
    assert resp.status_code == 200
    for chest_out in resp.json():
        assert "tier" not in chest_out
        assert "required_hero_level" not in chest_out
        assert "is_available_to_user" not in chest_out


# --- reward is capped by the opening hero's own tier --------------------------

async def test_reward_item_is_capped_by_heros_own_tier(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 8004, bot_token, level=21)  # tier 3
    await _fund(db_session, 8004, 100_000)
    chest = await create_chest(db_session, price=10)
    # Items exist above and within the hero's tier — the reward must never exceed tier 3.
    for tier in (1, 2, 3, 5):
        for rarity in Rarity:
            await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=tier, rarity=rarity)
    await db_session.commit()

    for _ in range(15):
        resp = await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers, json={})
        assert resp.status_code == 200
        assert resp.json()["reward"]["tier"] <= 3


async def test_pick_random_item_template_never_exceeds_max_tier(db_session):
    for tier in (1, 2):
        await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=tier, rarity=Rarity.common)
    await db_session.commit()

    for _ in range(10):
        template = await pick_random_item_template(db_session, max_tier=1, rarity=Rarity.legendary)  # no tier-1 legendary
        assert template.tier == 1  # falls back within max_tier, never above it


async def test_opening_a_chest_with_no_items_within_heros_tier_fails_cleanly(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 8005, bot_token, level=1)
    await _fund(db_session, 8005, 10_000)
    chest = await create_chest(db_session, price=10)
    await db_session.commit()  # no ItemTemplate rows at all

    resp = await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers, json={})
    assert resp.status_code == 409


# --- rarity probabilities and guaranteed minimum -----------------------------

def test_roll_rarity_respects_zero_weight_rarities():
    from app.models.chest import ChestRarityProbability

    probs = [
        ChestRarityProbability(rarity=Rarity.common, probability=1.0),
        ChestRarityProbability(rarity=Rarity.legendary, probability=0.0),
    ]
    for _ in range(50):
        assert roll_rarity(probs, None) == Rarity.common


def test_roll_rarity_guaranteed_minimum_is_always_honored():
    from app.models.chest import ChestRarityProbability

    probs = [
        ChestRarityProbability(rarity=Rarity.common, probability=0.97),
        ChestRarityProbability(rarity=Rarity.rare, probability=0.02),
        ChestRarityProbability(rarity=Rarity.epic, probability=0.01),
    ]
    for _ in range(200):
        rolled = roll_rarity(probs, Rarity.epic)
        assert rolled == Rarity.epic  # only epic meets-or-exceeds the minimum among configured rarities


async def test_guaranteed_min_rarity_chest_always_grants_at_least_that_rarity(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 8006, bot_token, level=1)
    await _fund(db_session, 8006, 100_000)
    chest = await create_chest(
        db_session, price=10, guaranteed_min_rarity=Rarity.epic,
        rarity_probabilities={Rarity.common: 0.9, Rarity.rare: 0.09, Rarity.epic: 0.01},
    )
    for rarity in Rarity:
        await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=rarity)
    await db_session.commit()

    from app.models.enums import RARITY_ORDER

    for _ in range(10):
        resp = await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers, json={})
        assert resp.status_code == 200
        assert RARITY_ORDER[Rarity(resp.json()["reward"]["rarity"])] >= RARITY_ORDER[Rarity.epic]


# --- coins / transactions / UserItem / inventory -----------------------------

async def test_opening_a_chest_debits_coins_and_creates_transaction(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 8007, bot_token, level=1)
    await _fund(db_session, 8007, 500)
    chest = await create_chest(db_session, price=150)
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()

    resp = await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers, json={})
    assert resp.status_code == 200
    assert resp.json()["balance"] == 350

    wallet = await client.get("/api/v1/economy", headers=headers)
    assert wallet.json()["coins"] == 350

    from sqlalchemy import select

    from app.models.transaction import CoinTransaction

    user = await get_user_by_telegram_id(db_session, 8007)
    txs = (
        await db_session.execute(select(CoinTransaction).where(CoinTransaction.user_id == user.id))
    ).scalars().all()
    assert len(txs) == 2  # admin_grant (funding) + chest_purchase
    purchase = next(t for t in txs if t.amount < 0)
    assert purchase.amount == -150
    assert purchase.related_object_type == "chest"
    assert purchase.related_object_id == chest.id


async def test_cannot_open_a_chest_without_enough_coins(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 8008, bot_token, level=1)
    await _fund(db_session, 8008, 50)
    chest = await create_chest(db_session, price=100)
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()

    resp = await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers, json={})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "insufficient_balance"


async def test_opened_item_appears_in_inventory_and_can_be_equipped(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 8009, bot_token, level=1)
    await _fund(db_session, 8009, 1000)
    chest = await create_chest(db_session, price=100)
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()

    open_resp = await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers, json={})
    item_id = open_resp.json()["reward"]["item_id"]

    inventory = await client.get("/api/v1/heroes/me/inventory", headers=headers)
    assert any(i["id"] == item_id for i in inventory.json())

    equip = await client.post(f"/api/v1/heroes/me/equipment/{item_id}/equip", headers=headers)
    assert equip.status_code == 200


# --- idempotency ---------------------------------------------------------------

async def test_duplicate_idempotency_key_does_not_double_charge_or_double_grant(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 8010, bot_token, level=1)
    await _fund(db_session, 8010, 500)
    chest = await create_chest(db_session, price=150)
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()

    first = await client.post(
        f"/api/v1/chests/{chest.id}/open", headers=headers, json={"idempotency_key": "retry-key-1"}
    )
    second = await client.post(
        f"/api/v1/chests/{chest.id}/open", headers=headers, json={"idempotency_key": "retry-key-1"}
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["opening_id"] == second.json()["opening_id"]
    assert first.json()["reward"]["item_id"] == second.json()["reward"]["item_id"]

    wallet = await client.get("/api/v1/economy", headers=headers)
    assert wallet.json()["coins"] == 350  # charged exactly once, not twice

    inventory = await client.get("/api/v1/heroes/me/inventory", headers=headers)
    assert len(inventory.json()) == 1  # granted exactly once


async def test_opening_history_lists_past_openings(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 8011, bot_token, level=1)
    await _fund(db_session, 8011, 1000)
    chest = await create_chest(db_session, price=100)
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()

    await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers, json={})
    await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers, json={})

    history = await client.get("/api/v1/chests/openings", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 2


async def test_unknown_chest_is_404(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 8012, bot_token, level=1)
    resp = await client.post("/api/v1/chests/999999/open", headers=headers, json={})
    assert resp.status_code == 404


async def test_opening_without_a_hero_is_404(client, bot_token):
    headers = telegram_headers(8013, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)  # registered, but never created a hero
    resp = await client.post("/api/v1/chests/1/open", headers=headers, json={})
    assert resp.status_code == 404


# --- the Stage 4 tier-dominance rule, still holding through the chest path ---

def test_tier_dominance_config_still_holds():
    assert_tier_dominance_holds()


@pytest.mark.parametrize("tier", range(1, MAX_TIER))
def test_common_next_tier_beats_legendary_this_tier_for_every_transition(tier):
    """Restated here (already covered exhaustively in test_item_progression.py)
    specifically because Stage 5 requires it re-verified in the context of
    chests actually drawing items — same formula, same function, not a
    second implementation (item_progression.item_power, unchanged)."""
    legendary_this_tier = item_power(tier, Rarity.legendary)
    common_next_tier = item_power(tier + 1, Rarity.common)
    assert common_next_tier > legendary_this_tier


# --- concurrency: two opens racing a balance that covers only one -----------

@pytest.mark.skip(
    reason=(
        "Same documented SQLite limitation as every other Stage 3/4/5 "
        "concurrency test — no real row-level locking on a shared "
        "StaticPool connection. Kept as executable documentation; the real "
        "enforcement was verified live against rpg-postgres — see the "
        "Stage 5 report."
    )
)
async def test_concurrent_chest_opens_with_balance_for_only_one_yield_exactly_one_success(
    client, db_session, bot_token
):
    from tests.conftest import TestSessionLocal

    hero_id, headers = await _make_hero(client, db_session, 8014, bot_token, level=1)
    await _fund(db_session, 8014, 100)  # enough for exactly one 100-coin chest
    chest = await create_chest(db_session, price=100)
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()

    user = await get_user_by_telegram_id(db_session, 8014)
    user_id, chest_id = user.id, chest.id

    async def attempt(key: str) -> str:
        async with TestSessionLocal() as session:
            from app.models.user import User as UserModel
            from app.services.hero_service import get_active_hero

            u = await session.get(UserModel, user_id)
            hero = await get_active_hero(session, u)
            try:
                await open_chest(session, u, hero, chest_id, key)
                return "ok"
            except Exception as exc:
                return type(exc).__name__

    results = await asyncio.gather(attempt("race-a"), attempt("race-b"))
    assert sorted(results) == ["InsufficientBalanceError", "ok"]

    async with TestSessionLocal() as session:
        refreshed = await get_user_by_telegram_id(session, 8014)
        assert refreshed.balance == 0
