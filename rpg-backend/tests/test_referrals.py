import asyncio

import pytest
from tests.factories import create_chest, create_class, create_hero_template, create_item_template, create_race, get_user_by_telegram_id
from tests.utils import telegram_headers

from app.models.enums import EquipmentSlot, Rarity, TransactionType
from app.models.user import User
from app.services.wallet_service import credit_coins


async def _register(client, telegram_id, bot_token, referral_code: str | None = None):
    headers = telegram_headers(telegram_id, bot_token)
    if referral_code is not None:
        headers = {**headers, "X-Referral-Code": referral_code}
    resp = await client.post("/api/v1/auth/session", headers=headers)
    assert resp.status_code == 200
    return headers, resp.json()


async def _make_hero(client, db_session, headers, telegram_id) -> int:
    # Distinct Race and CharacterClass per call — create_hero_template's
    # defaults (code="human"/"warrior") collide the moment a single test
    # creates more than one hero (both codes are unique columns), which
    # every referrer+referred test here does.
    race = await create_race(db_session, code=f"race-{telegram_id}")
    char_class = await create_class(db_session, code=f"class-{telegram_id}")
    template = await create_hero_template(db_session, name=f"Hero{telegram_id}", race=race, char_class=char_class)
    await db_session.commit()
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id, "name": "Герой"})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _fund(db_session, telegram_id, amount):
    user = await get_user_by_telegram_id(db_session, telegram_id)
    await credit_coins(db_session, user, amount, TransactionType.admin_grant)
    await db_session.commit()


async def _make_chest_with_loot(db_session, price=100):
    chest = await create_chest(db_session, price=price, slug=f"test-chest-{id(object())}")
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()
    return chest


# --- referral link creation --------------------------------------------------

async def test_registering_with_a_valid_referral_code_creates_the_link(client, db_session, bot_token):
    await _register(client, 30001, bot_token)  # referrer A
    referrer = await get_user_by_telegram_id(db_session, 30001)

    await _register(client, 30002, bot_token, referral_code=str(30001))  # referred B
    referred = await get_user_by_telegram_id(db_session, 30002)

    assert referred.referred_by_id == referrer.id
    assert referred.referral_reward_granted is False


async def test_registering_without_a_referral_code_has_no_link(client, db_session, bot_token):
    await _register(client, 30003, bot_token)
    user = await get_user_by_telegram_id(db_session, 30003)
    assert user.referred_by_id is None


async def test_malformed_referral_code_registration_still_succeeds(client, db_session, bot_token):
    _headers, body = await _register(client, 30004, bot_token, referral_code="not-a-number")
    assert body["user"]["id"] is not None  # registration succeeded, no error
    user = await get_user_by_telegram_id(db_session, 30004)
    assert user.referred_by_id is None


async def test_unknown_referral_code_registration_still_succeeds(client, db_session, bot_token):
    await _register(client, 30005, bot_token, referral_code="999999999")
    user = await get_user_by_telegram_id(db_session, 30005)
    assert user.referred_by_id is None


async def test_self_referral_is_ignored(client, db_session, bot_token):
    await _register(client, 30006, bot_token, referral_code=str(30006))
    user = await get_user_by_telegram_id(db_session, 30006)
    assert user.referred_by_id is None


async def test_repeated_session_does_not_change_an_existing_referral_link(client, db_session, bot_token):
    await _register(client, 30007, bot_token)  # A
    await _register(client, 30008, bot_token)  # C (a second, different potential referrer)
    await _register(client, 30009, bot_token, referral_code=str(30007))  # B -> referred by A

    referrer_a = await get_user_by_telegram_id(db_session, 30007)
    referrer_c = await get_user_by_telegram_id(db_session, 30008)

    # B logs in again, this time (implausibly) presenting C's code — must
    # not move the link.
    await _register(client, 30009, bot_token, referral_code=str(30008))
    referred = await get_user_by_telegram_id(db_session, 30009)
    assert referred.referred_by_id == referrer_a.id
    assert referred.referred_by_id != referrer_c.id


async def test_referral_code_and_count_appear_in_session_response(client, db_session, bot_token):
    _headers, body = await _register(client, 30010, bot_token)
    assert body["user"]["referral_code"] == "30010"
    assert body["user"]["referral_count"] == 0


# --- referral reward: trigger, amount, one-shot -------------------------------

async def test_first_chest_opening_grants_referrer_reward(client, db_session, bot_token):
    await _register(client, 30011, bot_token)  # A (referrer)
    headers_a = telegram_headers(30011, bot_token)
    await _make_hero(client, db_session, headers_a, 30011)

    headers_b, _ = await _register(client, 30012, bot_token, referral_code=str(30011))  # B (referred)
    hero_b = await _make_hero(client, db_session, headers_b, 30012)
    await _fund(db_session, 30012, 1000)
    chest = await _make_chest_with_loot(db_session, price=100)

    resp = await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers_b, json={})
    assert resp.status_code == 200

    wallet_a = await client.get("/api/v1/economy", headers=headers_a)
    assert wallet_a.json()["coins"] == 25

    hero_a_out = await client.get("/api/v1/heroes/me", headers=headers_a)
    assert hero_a_out.json()["xp"] == 0  # coins only, no XP

    referrer = await get_user_by_telegram_id(db_session, 30011)
    assert referrer is not None
    referred = await get_user_by_telegram_id(db_session, 30012)
    assert referred.referral_reward_granted is True


async def test_second_chest_opening_does_not_grant_the_reward_again(client, db_session, bot_token):
    await _register(client, 30013, bot_token)
    headers_a = telegram_headers(30013, bot_token)
    await _make_hero(client, db_session, headers_a, 30013)

    headers_b, _ = await _register(client, 30014, bot_token, referral_code=str(30013))
    await _make_hero(client, db_session, headers_b, 30014)
    await _fund(db_session, 30014, 1000)
    chest = await _make_chest_with_loot(db_session, price=50)

    await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers_b, json={})
    await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers_b, json={})

    wallet_a = await client.get("/api/v1/economy", headers=headers_a)
    assert wallet_a.json()["coins"] == 25  # granted exactly once, not twice


async def test_referrer_without_a_hero_does_not_break_chest_opening(client, db_session, bot_token):
    await _register(client, 30015, bot_token)  # A: registered, but never creates a hero

    headers_b, _ = await _register(client, 30016, bot_token, referral_code=str(30015))
    await _make_hero(client, db_session, headers_b, 30016)
    await _fund(db_session, 30016, 1000)
    chest = await _make_chest_with_loot(db_session, price=50)

    resp = await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers_b, json={})
    assert resp.status_code == 200  # B's chest opening is unaffected

    referrer = await get_user_by_telegram_id(db_session, 30015)
    assert referrer.balance == 0  # A never got a hero, so never got paid

    referred = await get_user_by_telegram_id(db_session, 30016)
    # Left False, not "consumed" — a hero-less referrer's reward is simply
    # never granted, not deferred/retried, per the Stage 10 design.
    assert referred.referral_reward_granted is False


async def test_no_referrer_no_reward_no_crash(client, db_session, bot_token):
    headers, _ = await _register(client, 30017, bot_token)
    await _make_hero(client, db_session, headers, 30017)
    await _fund(db_session, 30017, 1000)
    chest = await _make_chest_with_loot(db_session, price=50)

    resp = await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers, json={})
    assert resp.status_code == 200


async def test_free_chest_opening_also_triggers_the_referral_reward(client, db_session, bot_token):
    """The trigger is "any chest, paid or free" — not just paid ones."""
    await _register(client, 30018, bot_token)
    headers_a = telegram_headers(30018, bot_token)
    await _make_hero(client, db_session, headers_a, 30018)

    headers_b, _ = await _register(client, 30019, bot_token, referral_code=str(30018))
    await _make_hero(client, db_session, headers_b, 30019)
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await create_chest(db_session, price=0, slug="free-chest")
    await db_session.commit()

    resp = await client.get("/api/v1/chests/free", headers=headers_b)
    assert resp.json()["is_available"] is True
    claim = await client.post("/api/v1/chests/free/claim", headers=headers_b)
    assert claim.status_code == 200

    wallet_a = await client.get("/api/v1/economy", headers=headers_a)
    assert wallet_a.json()["coins"] == 25


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
async def test_concurrent_first_chest_openings_grant_the_referral_reward_exactly_once(client, db_session, bot_token):
    from tests.conftest import TestSessionLocal

    await _register(client, 30020, bot_token)
    headers_a = telegram_headers(30020, bot_token)
    await _make_hero(client, db_session, headers_a, 30020)

    headers_b, _ = await _register(client, 30021, bot_token, referral_code=str(30020))
    hero_b_id = await _make_hero(client, db_session, headers_b, 30021)
    await _fund(db_session, 30021, 10_000)
    chest = await _make_chest_with_loot(db_session, price=10)

    user_b = await get_user_by_telegram_id(db_session, 30021)
    user_b_id, chest_id = user_b.id, chest.id

    async def attempt(label: str) -> str:
        async with TestSessionLocal() as session:
            from app.services.chest_service import open_chest
            from app.services.hero_service import get_active_hero

            u = await session.get(User, user_b_id)
            hero = await get_active_hero(session, u)
            try:
                await open_chest(session, u, hero, chest_id, idempotency_key=None)
                return f"{label} ok"
            except Exception as exc:
                return f"{label} {type(exc).__name__}"

    results = await asyncio.gather(attempt("A"), attempt("B"))
    assert all("ok" in r for r in results)

    async with TestSessionLocal() as session:
        refreshed_referrer = await get_user_by_telegram_id(session, 30020)
        assert refreshed_referrer.balance == 25  # granted exactly once
