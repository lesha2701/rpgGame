"""Admin CRUD for the catalog resources added alongside admin_chests.py's
existing pattern: races, classes, hero-templates, enemies, items,
expeditions, quests. Also the first tests in this suite to exercise
get_current_admin at all — admin_chests.py itself had zero coverage before
this file (see tests/conftest.py's RPG_ADMIN_TELEGRAM_IDS addition)."""

from tests.utils import telegram_headers

from app.models.enums import EquipmentSlot, ItemStatType, QuestConditionType, Rarity

ADMIN_TELEGRAM_ID = 999000099
NON_ADMIN_TELEGRAM_ID = 40501


async def _admin_headers(client, bot_token) -> dict:
    headers = telegram_headers(ADMIN_TELEGRAM_ID, bot_token)
    resp = await client.post("/api/v1/auth/session", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["admin_token"] is not None, "RPG_ADMIN_TELEGRAM_IDS must include ADMIN_TELEGRAM_ID"
    return {"Authorization": f"Bearer {body['admin_token']}"}


# --- auth boundary (checked once — get_current_admin is shared by every
# admin_*.py router, no need to repeat this per resource) -------------------

async def test_admin_endpoint_requires_bearer_token(client, db_session):
    resp = await client.get("/api/v1/admin/races")
    assert resp.status_code == 401


async def test_admin_endpoint_rejects_non_admin_user(client, db_session, bot_token):
    headers = telegram_headers(NON_ADMIN_TELEGRAM_ID, bot_token)
    session = await client.post("/api/v1/auth/session", headers=headers)
    assert session.json()["admin_token"] is None

    # A non-admin has no admin_token to send at all — simulate someone
    # trying anyway with a well-formed but non-admin regular session token
    # doesn't apply here (admin auth is a distinct bearer scheme); the real
    # check is that regular users never receive a token in the first place.
    resp = await client.get("/api/v1/admin/races", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


# --- races -----------------------------------------------------------------

async def test_admin_race_crud(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)

    created = await client.post(
        "/api/v1/admin/races", headers=admin, json={"code": "dwarf", "name": "Дворф", "sort_order": 5}
    )
    assert created.status_code == 200, created.text
    race_id = created.json()["id"]
    assert created.json()["is_active"] is True

    listed = await client.get("/api/v1/admin/races", headers=admin)
    assert any(r["id"] == race_id for r in listed.json())

    updated = await client.put(f"/api/v1/admin/races/{race_id}", headers=admin, json={"name": "Гном"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Гном"

    toggled = await client.post(f"/api/v1/admin/races/{race_id}/toggle-active", headers=admin)
    assert toggled.json()["is_active"] is False

    # Deactivated races drop out of the public catalog immediately — no
    # separate publish step, matches every other is_active flag in this app.
    public = await client.get("/api/v1/races", headers=telegram_headers(999000001, bot_token))
    assert all(r["code"] != "dwarf" for r in public.json())


# --- classes -----------------------------------------------------------

async def test_admin_class_crud(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)

    created = await client.post(
        "/api/v1/admin/classes",
        headers=admin,
        json={
            "code": "paladin",
            "name": "Паладин",
            "base_hp": 140,
            "base_attack": 9,
            "base_defense": 12,
            "base_speed": 6,
            "hp_per_level": 6,
            "attack_per_level": 1,
            "defense_per_level": 1.5,
            "speed_per_level": 0.2,
        },
    )
    assert created.status_code == 200, created.text
    class_id = created.json()["id"]

    updated = await client.put(f"/api/v1/admin/classes/{class_id}", headers=admin, json={"base_hp": 150})
    assert updated.json()["base_hp"] == 150

    toggled = await client.post(f"/api/v1/admin/classes/{class_id}/toggle-active", headers=admin)
    assert toggled.json()["is_active"] is False


# --- hero templates ----------------------------------------------------

async def test_admin_hero_template_crud(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)

    race = await client.post("/api/v1/admin/races", headers=admin, json={"code": "elf_ht", "name": "Эльф"})
    char_class = await client.post(
        "/api/v1/admin/classes",
        headers=admin,
        json={
            "code": "ranger_ht",
            "name": "Следопыт",
            "base_hp": 100,
            "base_attack": 12,
            "base_defense": 6,
            "base_speed": 10,
            "hp_per_level": 4,
            "attack_per_level": 1.2,
            "defense_per_level": 0.5,
            "speed_per_level": 0.4,
        },
    )
    race_id, class_id = race.json()["id"], char_class.json()["id"]

    created = await client.post(
        "/api/v1/admin/hero-templates",
        headers=admin,
        json={"race_id": race_id, "class_id": class_id, "name": "Леголас"},
    )
    assert created.status_code == 200, created.text
    template_id = created.json()["id"]
    # Nested race/character_class must be populated (lazy="joined" re-fetch).
    assert created.json()["race"]["code"] == "elf_ht"
    assert created.json()["character_class"]["code"] == "ranger_ht"

    updated = await client.put(
        f"/api/v1/admin/hero-templates/{template_id}", headers=admin, json={"name": "Леголас Гринлиф"}
    )
    assert updated.json()["name"] == "Леголас Гринлиф"

    toggled = await client.post(f"/api/v1/admin/hero-templates/{template_id}/toggle-active", headers=admin)
    assert toggled.json()["is_active"] is False


# --- enemies -------------------------------------------------------------

async def test_admin_enemy_crud(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)

    created = await client.post(
        "/api/v1/admin/enemies",
        headers=admin,
        json={
            "name": "Тестовый тролль",
            "level": 8,
            "hp": 300,
            "attack": 20,
            "defense": 10,
            "speed": 5,
            "reward_xp": 60,
            "reward_coins": 40,
        },
    )
    assert created.status_code == 200, created.text
    enemy_id = created.json()["id"]

    updated = await client.put(f"/api/v1/admin/enemies/{enemy_id}", headers=admin, json={"hp": 350})
    assert updated.json()["hp"] == 350

    toggled = await client.post(f"/api/v1/admin/enemies/{enemy_id}/toggle-active", headers=admin)
    assert toggled.json()["is_active"] is False


# --- items ---------------------------------------------------------------

async def test_admin_item_crud_with_affixes(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)

    created = await client.post(
        "/api/v1/admin/items",
        headers=admin,
        json={
            "slot": EquipmentSlot.ring.value,
            "tier": 3,
            "rarity": Rarity.epic.value,
            "name": "Кольцо тестового могущества",
            "affix_stat_types": [ItemStatType.attack.value, ItemStatType.speed.value],
        },
    )
    assert created.status_code == 200, created.text
    item_id = created.json()["id"]
    assert {a["stat_type"] for a in created.json()["affixes"]} == {"attack", "speed"}

    updated = await client.put(
        f"/api/v1/admin/items/{item_id}",
        headers=admin,
        json={"affix_stat_types": [ItemStatType.defense.value]},
    )
    assert updated.status_code == 200
    assert [a["stat_type"] for a in updated.json()["affixes"]] == ["defense"]

    toggled = await client.post(f"/api/v1/admin/items/{item_id}/toggle-active", headers=admin)
    assert toggled.json()["is_active"] is False


# --- expeditions ---------------------------------------------------------

async def test_admin_expedition_crud(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)

    created = await client.post(
        "/api/v1/admin/expeditions",
        headers=admin,
        json={
            "name": "Тестовый поход",
            "duration_seconds": 600,
            "required_hero_level": 2,
            "reward_xp": 30,
            "reward_coins": 15,
        },
    )
    assert created.status_code == 200, created.text
    expedition_id = created.json()["id"]

    updated = await client.put(
        f"/api/v1/admin/expeditions/{expedition_id}", headers=admin, json={"duration_seconds": 900}
    )
    assert updated.json()["duration_seconds"] == 900

    toggled = await client.post(f"/api/v1/admin/expeditions/{expedition_id}/toggle-active", headers=admin)
    assert toggled.json()["is_active"] is False


# --- quests ----------------------------------------------------------------

async def test_admin_quest_crud(client, db_session, bot_token):
    admin = await _admin_headers(client, bot_token)

    created = await client.post(
        "/api/v1/admin/quests",
        headers=admin,
        json={
            "code": "admin_test_quest",
            "name": "Тестовый квест",
            "condition_type": QuestConditionType.battles_won.value,
            "target_value": 3,
            "reward_xp": 10,
            "reward_coins": 5,
        },
    )
    assert created.status_code == 200, created.text
    quest_id = created.json()["id"]

    updated = await client.put(f"/api/v1/admin/quests/{quest_id}", headers=admin, json={"target_value": 5})
    assert updated.json()["target_value"] == 5

    toggled = await client.post(f"/api/v1/admin/quests/{quest_id}/toggle-active", headers=admin)
    assert toggled.json()["is_active"] is False
