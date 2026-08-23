from tests.factories import (
    create_chest,
    create_class,
    create_enemy_template,
    create_expedition_template,
    create_hero_template,
    create_item_template,
    create_quest_definition,
    create_race,
    get_user_by_telegram_id,
)
from tests.utils import telegram_headers

from app.models.enums import EquipmentSlot, QuestConditionType, Rarity, TransactionType
from app.services.wallet_service import credit_coins


async def _register(client, telegram_id, bot_token, referral_code: str | None = None):
    headers = telegram_headers(telegram_id, bot_token)
    if referral_code is not None:
        headers = {**headers, "X-Referral-Code": referral_code}
    resp = await client.post("/api/v1/auth/session", headers=headers)
    assert resp.status_code == 200
    return headers


async def _make_hero(client, db_session, telegram_id, bot_token) -> int:
    race = await create_race(db_session, code=f"race-{telegram_id}")
    char_class = await create_class(db_session, code=f"class-{telegram_id}")
    template = await create_hero_template(db_session, name=f"Hero{telegram_id}", race=race, char_class=char_class)
    await db_session.commit()
    headers = telegram_headers(telegram_id, bot_token)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id, "name": "Герой"})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _fund(db_session, telegram_id, amount):
    user = await get_user_by_telegram_id(db_session, telegram_id)
    await credit_coins(db_session, user, amount, TransactionType.admin_grant)
    await db_session.commit()


# --- private profile: empty states --------------------------------------------

async def test_profile_of_a_fresh_user_with_no_hero(client, db_session, bot_token):
    headers = await _register(client, 40001, bot_token)
    resp = await client.get("/api/v1/profile/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["active_hero"] is None
    assert body["balance"] == 0
    stats = body["statistics"]
    assert stats["battles"] == {"played": 0, "wins": 0, "losses": 0}
    assert stats["arena"] == {"played": 0, "wins": 0, "losses": 0}
    assert stats["expeditions"] == {"started": 0, "claimed": 0}
    assert stats["quests"] == {"claimed": 0}
    assert stats["chests"] == {"opened": 0}
    assert stats["referrals"] == {"referral_count": 0, "successful_referrals": 0}


async def test_profile_reflects_hero_and_balance(client, db_session, bot_token):
    headers = await _register(client, 40002, bot_token)
    await _make_hero(client, db_session, 40002, bot_token)
    await _fund(db_session, 40002, 250)

    resp = await client.get("/api/v1/profile/me", headers=headers)
    body = resp.json()
    assert body["user"]["active_hero"]["level"] == 1
    assert body["balance"] == 250


# --- statistics: battles ----------------------------------------------------

async def test_profile_battle_statistics(client, db_session, bot_token):
    headers = await _register(client, 40003, bot_token)
    await _make_hero(client, db_session, 40003, bot_token)

    winnable = await create_enemy_template(db_session, name="Weak", hp=1, attack=1, defense=0, speed=1)
    unwinnable = await create_enemy_template(
        db_session, name="Strong", hp=100000, attack=99999, defense=0, speed=99
    )
    await db_session.commit()

    await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": winnable.id})
    await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": unwinnable.id})

    resp = await client.get("/api/v1/profile/me", headers=headers)
    battles = resp.json()["statistics"]["battles"]
    assert battles == {"played": 2, "wins": 1, "losses": 1}


# --- statistics: expeditions -------------------------------------------------

async def test_profile_expedition_statistics(client, db_session, bot_token):
    from datetime import datetime, timedelta, timezone

    from app.models.user_expedition import UserExpedition

    headers = await _register(client, 40004, bot_token)
    await _make_hero(client, db_session, 40004, bot_token)
    expedition = await create_expedition_template(db_session, name="Quick", duration_seconds=1)
    await db_session.commit()

    started = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
    user_expedition_id = started.json()["id"]

    resp = await client.get("/api/v1/profile/me", headers=headers)
    assert resp.json()["statistics"]["expeditions"] == {"started": 1, "claimed": 0}

    row = await db_session.get(UserExpedition, user_expedition_id)
    row.completed_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.add(row)
    await db_session.commit()
    await client.post(f"/api/v1/expeditions/{user_expedition_id}/claim", headers=headers)

    resp = await client.get("/api/v1/profile/me", headers=headers)
    assert resp.json()["statistics"]["expeditions"] == {"started": 1, "claimed": 1}


# --- statistics: quests ------------------------------------------------------

async def test_profile_quest_statistics(client, db_session, bot_token):
    headers = await _register(client, 40005, bot_token)
    await _make_hero(client, db_session, 40005, bot_token)
    enemy = await create_enemy_template(db_session, name="Weak", hp=1, attack=1, defense=0, speed=1)
    await create_quest_definition(
        db_session, code="q1", condition_type=QuestConditionType.battles_won, target_value=1
    )
    await db_session.commit()

    await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id})
    listed = await client.get("/api/v1/quests", headers=headers)
    user_quest_id = next(q["id"] for q in listed.json() if q["code"] == "q1")
    await client.post(f"/api/v1/quests/{user_quest_id}/claim", headers=headers)

    resp = await client.get("/api/v1/profile/me", headers=headers)
    assert resp.json()["statistics"]["quests"] == {"claimed": 1}


# --- statistics: chests -------------------------------------------------------

async def test_profile_chest_statistics(client, db_session, bot_token):
    headers = await _register(client, 40006, bot_token)
    await _make_hero(client, db_session, 40006, bot_token)
    chest = await create_chest(db_session, price=0, slug=f"chest-{40006}")
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()

    await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers, json={})

    resp = await client.get("/api/v1/profile/me", headers=headers)
    assert resp.json()["statistics"]["chests"] == {"opened": 1}


# --- statistics: arena --------------------------------------------------------

async def test_profile_arena_statistics(client, db_session, bot_token):
    race = await create_race(db_session, code="race-arena-profile")
    strong = await create_class(
        db_session, code="strong-arena-profile", base_attack=1000, base_defense=0, base_hp=1000,
        base_speed=20, base_crit_chance=0.0,
    )
    weak = await create_class(
        db_session, code="weak-arena-profile", base_attack=1, base_defense=0, base_hp=1, base_speed=1,
        base_crit_chance=0.0,
    )
    template_a = await create_hero_template(db_session, name="StrongHero", race=race, char_class=strong)
    template_b = await create_hero_template(db_session, name="WeakHero", race=race, char_class=weak)
    await db_session.commit()

    headers_a = await _register(client, 40007, bot_token)
    resp_a = await client.post("/api/v1/heroes", headers=headers_a, json={"hero_template_id": template_a.id, "name": "Герой"})
    assert resp_a.status_code == 201

    headers_b = await _register(client, 40008, bot_token)
    resp_b = await client.post("/api/v1/heroes", headers=headers_b, json={"hero_template_id": template_b.id, "name": "Герой"})
    assert resp_b.status_code == 201
    user_b = await get_user_by_telegram_id(db_session, 40008)

    match = await client.post("/api/v1/arena/matches", headers=headers_a, json={"opponent_user_id": user_b.id})
    match_id = match.json()["id"]
    await client.post(f"/api/v1/arena/matches/{match_id}/action", headers=headers_a, json={"round": 1, "action_type": "basic_attack"})
    await client.post(f"/api/v1/arena/matches/{match_id}/action", headers=headers_b, json={"round": 1, "action_type": "basic_attack"})

    profile_a = await client.get("/api/v1/profile/me", headers=headers_a)
    assert profile_a.json()["statistics"]["arena"] == {"played": 1, "wins": 1, "losses": 0}

    profile_b = await client.get("/api/v1/profile/me", headers=headers_b)
    assert profile_b.json()["statistics"]["arena"] == {"played": 1, "wins": 0, "losses": 1}


# --- statistics: referrals ---------------------------------------------------

async def test_profile_referral_statistics(client, db_session, bot_token):
    headers_a = await _register(client, 40009, bot_token)
    await _make_hero(client, db_session, 40009, bot_token)

    headers_b = await _register(client, 40010, bot_token, referral_code=str(40009))
    await _make_hero(client, db_session, 40010, bot_token)
    chest = await create_chest(db_session, price=0, slug="chest-referral-profile")
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()

    profile_before = await client.get("/api/v1/profile/me", headers=headers_a)
    assert profile_before.json()["statistics"]["referrals"] == {"referral_count": 1, "successful_referrals": 0}

    await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers_b, json={})

    profile_after = await client.get("/api/v1/profile/me", headers=headers_a)
    assert profile_after.json()["statistics"]["referrals"] == {"referral_count": 1, "successful_referrals": 1}


# --- public profile ------------------------------------------------------------

async def test_public_profile_shows_expected_fields(client, db_session, bot_token):
    headers_a = await _register(client, 40011, bot_token)
    await _make_hero(client, db_session, 40011, bot_token)
    user_a = await get_user_by_telegram_id(db_session, 40011)

    headers_b = await _register(client, 40012, bot_token)

    resp = await client.get(f"/api/v1/profile/{user_a.id}", headers=headers_b)
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == user_a.id
    assert body["hero"]["level"] == 1
    assert body["hero"]["name"]
    assert body["hero"]["race"]
    assert body["hero"]["character_class"]
    assert set(body["statistics"].keys()) == {
        "arena_wins", "pve_wins", "campaign_nodes_cleared", "expeditions_claimed", "quests_claimed", "chests_opened",
    }


async def test_public_profile_excludes_private_fields(client, db_session, bot_token):
    headers_a = await _register(client, 40013, bot_token)
    await _make_hero(client, db_session, 40013, bot_token)
    await _fund(db_session, 40013, 999)
    user_a = await get_user_by_telegram_id(db_session, 40013)

    headers_b = await _register(client, 40014, bot_token)
    resp = await client.get(f"/api/v1/profile/{user_a.id}", headers=headers_b)
    body = resp.json()
    assert "telegram_id" not in body
    assert "balance" not in body
    assert "referral_code" not in body
    assert "referral_count" not in body


async def test_public_profile_user_without_hero(client, db_session, bot_token):
    await _register(client, 40015, bot_token)
    user = await get_user_by_telegram_id(db_session, 40015)

    headers_viewer = await _register(client, 40016, bot_token)
    resp = await client.get(f"/api/v1/profile/{user.id}", headers=headers_viewer)
    assert resp.status_code == 200
    assert resp.json()["hero"] is None


async def test_public_profile_unknown_user_is_404(client, db_session, bot_token):
    headers = await _register(client, 40017, bot_token)
    resp = await client.get("/api/v1/profile/999999", headers=headers)
    assert resp.status_code == 404
