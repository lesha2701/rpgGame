import asyncio

import pytest
from tests.factories import (
    create_class,
    create_hero_template,
    create_item_template,
    create_race,
    get_user_by_telegram_id,
    grant_item_to_user,
    set_hero_level,
)
from tests.utils import telegram_headers

from app.models.enums import EquipmentSlot, ItemStatType, Rarity
from app.services.inventory_service import equip_item, get_inventory


async def _register_user(client, telegram_id, bot_token):
    headers = telegram_headers(telegram_id, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    return headers


async def _make_hero(client, db_session, telegram_id, bot_token):
    # Unique race/class codes per telegram_id: this helper is sometimes
    # called twice in one test (e.g. "another user's hero"), and the
    # factories' defaults (fixed codes "human"/"warrior") would collide on
    # races.code/character_classes.code the second time otherwise.
    race = await create_race(db_session, code=f"race{telegram_id}", name="Раса")
    char_class = await create_class(db_session, code=f"class{telegram_id}", name="Класс")
    template = await create_hero_template(
        db_session, name=f"Герой{telegram_id}", race=race, char_class=char_class
    )
    await db_session.commit()
    headers = await _register_user(client, telegram_id, bot_token)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id})
    assert resp.status_code == 201
    return resp.json()["id"], headers


async def _grant_and_get_id(db_session, user, template) -> int:
    item = await grant_item_to_user(db_session, user, template)
    await db_session.commit()
    return item.id


# --- catalog -----------------------------------------------------------------

async def test_item_template_catalog_lists_active_items(client, db_session, bot_token):
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await create_item_template(db_session, slot=EquipmentSlot.boots, tier=2, rarity=Rarity.rare)
    await db_session.commit()

    resp = await client.get("/api/v1/item-templates", headers=telegram_headers(6001, bot_token))
    assert resp.status_code == 200
    slots = {i["slot"] for i in resp.json()}
    assert {"weapon", "boots"} <= slots


async def test_item_template_catalog_filters_by_tier_and_slot(client, db_session, bot_token):
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=2, rarity=Rarity.common)
    await create_item_template(db_session, slot=EquipmentSlot.boots, tier=1, rarity=Rarity.common)
    await db_session.commit()

    resp = await client.get("/api/v1/item-templates?tier=1&slot=weapon", headers=telegram_headers(6002, bot_token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["tier"] == 1
    assert body[0]["slot"] == "weapon"


async def test_item_template_out_includes_required_level_stats_and_affixes(client, db_session, bot_token):
    template = await create_item_template(
        db_session, slot=EquipmentSlot.armor, tier=3, rarity=Rarity.epic,
        affix_stat_types=[ItemStatType.hp, ItemStatType.speed],
    )
    await db_session.commit()

    resp = await client.get("/api/v1/item-templates?tier=3", headers=telegram_headers(6003, bot_token))
    body = next(i for i in resp.json() if i["id"] == template.id)
    assert body["required_hero_level"] == 21  # tier 3 -> (3-1)*10+1
    assert body["stats"]["hp"] > 0 or body["stats"]["defense"] > 0
    assert len(body["affixes"]) == 2


# --- inventory -----------------------------------------------------------------

async def test_inventory_lists_owned_items_including_unequipped(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 6010, bot_token)
    user = await get_user_by_telegram_id(db_session, 6010)
    template = await create_item_template(db_session)
    await db_session.commit()
    await _grant_and_get_id(db_session, user, template)

    resp = await client.get("/api/v1/heroes/me/inventory", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["is_equipped"] is False


async def test_inventory_item_detail_404_for_unknown_item(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 6011, bot_token)
    resp = await client.get("/api/v1/heroes/me/inventory/999999", headers=headers)
    assert resp.status_code == 404


# --- equip / unequip -----------------------------------------------------------

async def test_equip_an_item_within_level_range(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 6020, bot_token)
    user = await get_user_by_telegram_id(db_session, 6020)
    template = await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()
    item_id = await _grant_and_get_id(db_session, user, template)

    resp = await client.post(f"/api/v1/heroes/me/equipment/{item_id}/equip", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_equipped"] is True
    assert resp.json()["equipped_hero_id"] == hero_id

    equipment = await client.get("/api/v1/heroes/me/equipment", headers=headers)
    assert equipment.json()["weapon"]["id"] == item_id


async def test_equip_raises_hero_final_stats(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 6021, bot_token)
    user = await get_user_by_telegram_id(db_session, 6021)
    before = (await client.get("/api/v1/heroes/me", headers=headers)).json()["stats"]["attack"]

    template = await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()
    item_id = await _grant_and_get_id(db_session, user, template)
    await client.post(f"/api/v1/heroes/me/equipment/{item_id}/equip", headers=headers)

    after = (await client.get("/api/v1/heroes/me", headers=headers)).json()["stats"]["attack"]
    assert after > before


async def test_equip_with_fractional_item_power_does_not_500(client, db_session, bot_token):
    """Regression test: tier 3's item_power (10 * 2.2^2 = 48.4) is not a
    whole number, and HeroStatsOut's hp/attack/defense/speed fields are
    ints — combining a fractional item contribution with the (integer)
    class stats used to raise a pydantic ValidationError (int_from_float)
    the first time this was exercised live against Postgres, because every
    other test's item_power happened to land on a whole number by
    coincidence (tier 1/2 with common/rare rarity are integers; tier 3+
    generally isn't). hero_service.hero_to_out rounds the combined total
    once at the end specifically to fix this."""
    hero_id, headers = await _make_hero(client, db_session, 6099, bot_token)
    user = await get_user_by_telegram_id(db_session, 6099)
    await set_hero_level(db_session, hero_id, 21)  # tier 3 requires level 21
    await db_session.commit()

    template = await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=3, rarity=Rarity.common)
    await db_session.commit()
    item_id = await _grant_and_get_id(db_session, user, template)

    resp = await client.post(f"/api/v1/heroes/me/equipment/{item_id}/equip", headers=headers)
    assert resp.status_code == 200

    hero_resp = await client.get("/api/v1/heroes/me", headers=headers)
    assert hero_resp.status_code == 200
    assert isinstance(hero_resp.json()["stats"]["attack"], int)


async def test_equipping_a_second_item_in_the_same_slot_swaps_it(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 6022, bot_token)
    user = await get_user_by_telegram_id(db_session, 6022)
    template = await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()
    sword1 = await _grant_and_get_id(db_session, user, template)
    sword2 = await _grant_and_get_id(db_session, user, template)

    await client.post(f"/api/v1/heroes/me/equipment/{sword1}/equip", headers=headers)
    resp = await client.post(f"/api/v1/heroes/me/equipment/{sword2}/equip", headers=headers)
    assert resp.status_code == 200

    equipment = await client.get("/api/v1/heroes/me/equipment", headers=headers)
    assert equipment.json()["weapon"]["id"] == sword2

    inventory = await client.get("/api/v1/heroes/me/inventory", headers=headers)
    by_id = {i["id"]: i for i in inventory.json()}
    assert by_id[sword1]["is_equipped"] is False
    assert by_id[sword2]["is_equipped"] is True


async def test_unequip_returns_item_to_inventory(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 6023, bot_token)
    user = await get_user_by_telegram_id(db_session, 6023)
    template = await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()
    item_id = await _grant_and_get_id(db_session, user, template)
    await client.post(f"/api/v1/heroes/me/equipment/{item_id}/equip", headers=headers)

    resp = await client.post(f"/api/v1/heroes/me/equipment/{item_id}/unequip", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_equipped"] is False

    equipment = await client.get("/api/v1/heroes/me/equipment", headers=headers)
    assert equipment.json()["weapon"] is None


async def test_cannot_equip_item_above_heros_level(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 6024, bot_token)
    user = await get_user_by_telegram_id(db_session, 6024)
    high_tier = await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=3, rarity=Rarity.common)
    await db_session.commit()
    item_id = await _grant_and_get_id(db_session, user, high_tier)

    resp = await client.post(f"/api/v1/heroes/me/equipment/{item_id}/equip", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_equip_becomes_possible_after_reaching_the_required_level(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 6025, bot_token)
    user = await get_user_by_telegram_id(db_session, 6025)
    high_tier = await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=3, rarity=Rarity.common)
    await db_session.commit()
    item_id = await _grant_and_get_id(db_session, user, high_tier)

    await set_hero_level(db_session, hero_id, 21)
    await db_session.commit()

    resp = await client.post(f"/api/v1/heroes/me/equipment/{item_id}/equip", headers=headers)
    assert resp.status_code == 200


async def test_equipping_an_item_you_dont_own_is_404(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 6026, bot_token)
    other_hero_id, other_headers = await _make_hero(client, db_session, 6027, bot_token)
    other_user = await get_user_by_telegram_id(db_session, 6027)
    template = await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()
    other_item_id = await _grant_and_get_id(db_session, other_user, template)

    resp = await client.post(f"/api/v1/heroes/me/equipment/{other_item_id}/equip", headers=headers)
    assert resp.status_code == 404


async def test_unequipping_an_item_not_equipped_here_is_404(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 6028, bot_token)
    user = await get_user_by_telegram_id(db_session, 6028)
    template = await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()
    item_id = await _grant_and_get_id(db_session, user, template)  # never equipped

    resp = await client.post(f"/api/v1/heroes/me/equipment/{item_id}/unequip", headers=headers)
    assert resp.status_code == 404


async def test_equipping_the_same_item_twice_is_idempotent(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 6029, bot_token)
    user = await get_user_by_telegram_id(db_session, 6029)
    template = await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()
    item_id = await _grant_and_get_id(db_session, user, template)

    first = await client.post(f"/api/v1/heroes/me/equipment/{item_id}/equip", headers=headers)
    second = await client.post(f"/api/v1/heroes/me/equipment/{item_id}/equip", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200


# --- concurrent equip into the same slot ----------------------------------------

@pytest.mark.skip(
    reason=(
        "Same documented limitation as test_skills.py's concurrency test: "
        "SQLite's shared StaticPool connection doesn't exercise real "
        "row-level locking. Kept as executable documentation; the real "
        "enforcement was verified live against rpg-postgres with two "
        "genuinely separate connections — see the Stage 4 report."
    )
)
async def test_concurrent_equips_into_the_same_slot_never_both_land(client, db_session, bot_token):
    from tests.conftest import TestSessionLocal

    hero_id, headers = await _make_hero(client, db_session, 6030, bot_token)
    user = await get_user_by_telegram_id(db_session, 6030)
    template = await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()
    sword1 = await _grant_and_get_id(db_session, user, template)
    sword2 = await _grant_and_get_id(db_session, user, template)

    async def attempt(item_id: int) -> str:
        async with TestSessionLocal() as session:
            try:
                await equip_item(session, hero_id, item_id)
                return "ok"
            except Exception as exc:
                return type(exc).__name__

    results = await asyncio.gather(attempt(sword1), attempt(sword2))
    # Both may legitimately succeed sequentially (equip is a swap, not a
    # conflict) IF they serialize correctly — the real property under test
    # is that the DB never ends up with two items equipped in the same slot
    # at once, checked below regardless of which interleaving happened.
    assert "ok" in results

    async with TestSessionLocal() as session:
        equipped = await get_inventory(session, user.id)
        equipped_in_weapon_slot = [i for i in equipped if i.equipped_hero_id == hero_id and i.slot == EquipmentSlot.weapon]
        assert len(equipped_in_weapon_slot) <= 1
