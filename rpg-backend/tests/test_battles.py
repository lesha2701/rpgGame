import asyncio

import pytest
from tests.factories import create_class, create_enemy_template, create_hero_template, create_skill_definition, set_hero_level
from tests.utils import telegram_headers

from app.services.progression import xp_to_next_level


async def _make_hero(client, db_session, telegram_id, bot_token, level: int = 1, char_class=None):
    template = await create_hero_template(db_session, name=f"Герой{telegram_id}", char_class=char_class)
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


# --- winning a battle grants XP + coins via the existing services ------------

async def test_winning_a_battle_grants_xp_and_coins(client, db_session, bot_token):
    enemy = await create_enemy_template(
        db_session, name="Слабый враг", level=1, hp=1, attack=1, defense=0, speed=1, reward_xp=15, reward_coins=10
    )
    _hero_id, headers = await _make_hero(client, db_session, 9001, bot_token, level=1)
    await db_session.commit()

    resp = await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id})
    assert resp.status_code == 201
    body = resp.json()
    assert body["result"] == "won"
    assert body["reward_xp"] == 15
    assert body["reward_coins"] == 10
    assert body["hero_level"] == 1
    assert body["hero_xp"] == 15
    assert body["balance"] == 10
    assert len(body["log"]) >= 1

    wallet = await client.get("/api/v1/economy", headers=headers)
    assert wallet.json()["coins"] == 10


async def test_losing_a_battle_grants_no_reward_and_does_not_touch_hero_state(client, db_session, bot_token):
    enemy = await create_enemy_template(
        db_session, name="Убийца", level=1, hp=100000, attack=99999, defense=0, speed=99, reward_xp=50, reward_coins=50
    )
    _hero_id, headers = await _make_hero(client, db_session, 9002, bot_token, level=1)
    await db_session.commit()

    resp = await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id})
    assert resp.status_code == 201
    body = resp.json()
    assert body["result"] == "lost"
    assert body["reward_xp"] == 0
    assert body["reward_coins"] == 0
    assert body["hero_level"] == 1
    assert body["hero_xp"] == 0
    assert body["balance"] == 0


async def test_a_battle_can_level_up_the_hero(client, db_session, bot_token):
    enemy = await create_enemy_template(
        db_session, name="Опытный враг", level=1, hp=1, attack=1, defense=0, speed=1,
        reward_xp=xp_to_next_level(1), reward_coins=0,
    )
    _hero_id, headers = await _make_hero(client, db_session, 9003, bot_token, level=1)
    await db_session.commit()

    resp = await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id})
    assert resp.status_code == 201
    body = resp.json()
    assert body["hero_level"] == 2
    assert body["hero_xp"] == 0


async def test_a_learned_skill_can_be_used_in_battle(client, db_session, bot_token):
    char_class = await create_class(db_session, code="cls9004", name="ТестКласс")
    skill = await create_skill_definition(db_session, char_class, code="s1", name="Навык", required_hero_level=1)
    template = await create_hero_template(db_session, name="Герой9004", char_class=char_class)
    await db_session.commit()
    headers = telegram_headers(9004, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    create_resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id})
    assert create_resp.status_code == 201
    upgrade_resp = await client.post(f"/api/v1/heroes/me/skills/{skill.id}/upgrade", headers=headers)
    assert upgrade_resp.status_code == 200

    enemy = await create_enemy_template(db_session, name="Мишень", level=1, hp=1, attack=1, defense=0, speed=1)
    await db_session.commit()

    resp = await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id})
    assert resp.status_code == 201
    log = resp.json()["log"]
    assert any(entry["skill_id"] == skill.id for entry in log)


# --- validation / gating ------------------------------------------------------

async def test_cannot_challenge_an_enemy_above_heros_level(client, db_session, bot_token):
    enemy = await create_enemy_template(db_session, name="Сильный враг", level=5)
    _hero_id, headers = await _make_hero(client, db_session, 9005, bot_token, level=1)
    await db_session.commit()

    resp = await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_inactive_enemy_is_rejected(client, db_session, bot_token):
    enemy = await create_enemy_template(db_session, name="Неактивный враг", level=1, is_active=False)
    _hero_id, headers = await _make_hero(client, db_session, 9006, bot_token, level=1)
    await db_session.commit()

    resp = await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id})
    assert resp.status_code == 409


async def test_unknown_enemy_is_404(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 9007, bot_token, level=1)
    await db_session.commit()

    resp = await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": 999999})
    assert resp.status_code == 404


async def test_starting_a_battle_without_a_hero_is_404(client, bot_token):
    headers = telegram_headers(9008, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": 1})
    assert resp.status_code == 404


# --- idempotency ---------------------------------------------------------------

async def test_duplicate_idempotency_key_does_not_double_grant_rewards(client, db_session, bot_token):
    enemy = await create_enemy_template(
        db_session, name="Слабый враг", level=1, hp=1, attack=1, defense=0, speed=1, reward_xp=15, reward_coins=10
    )
    _hero_id, headers = await _make_hero(client, db_session, 9009, bot_token, level=1)
    await db_session.commit()

    first = await client.post(
        "/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id, "idempotency_key": "battle-key-1"}
    )
    second = await client.post(
        "/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id, "idempotency_key": "battle-key-1"}
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    wallet = await client.get("/api/v1/economy", headers=headers)
    assert wallet.json()["coins"] == 10  # granted exactly once, not twice

    heroes_me = await client.get("/api/v1/heroes/me", headers=headers)
    assert heroes_me.json()["xp"] == 15


# --- history / detail ----------------------------------------------------------

async def test_battle_history_lists_past_battles_newest_first(client, db_session, bot_token):
    enemy = await create_enemy_template(db_session, name="Слабый враг", level=1, hp=1, attack=1, defense=0, speed=1)
    _hero_id, headers = await _make_hero(client, db_session, 9010, bot_token, level=1)
    await db_session.commit()

    first = await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id})
    second = await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id})

    history = await client.get("/api/v1/battles", headers=headers)
    assert history.status_code == 200
    ids = [b["id"] for b in history.json()]
    assert ids == [second.json()["id"], first.json()["id"]]


async def test_battle_detail_matches_the_creation_response(client, db_session, bot_token):
    enemy = await create_enemy_template(db_session, name="Слабый враг", level=1, hp=1, attack=1, defense=0, speed=1)
    _hero_id, headers = await _make_hero(client, db_session, 9011, bot_token, level=1)
    await db_session.commit()

    created = await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id})
    battle_id = created.json()["id"]

    detail = await client.get(f"/api/v1/battles/{battle_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["result"] == created.json()["result"]
    assert detail.json()["log"] == created.json()["log"]


async def test_unknown_battle_id_is_404(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 9012, bot_token, level=1)
    await db_session.commit()

    resp = await client.get("/api/v1/battles/999999", headers=headers)
    assert resp.status_code == 404


# --- concurrency: two identical requests must yield exactly one battle -------

@pytest.mark.skip(
    reason=(
        "Same documented SQLite limitation as every other Stage 3/4/5/6 "
        "concurrency test — no real row-level locking on a shared "
        "StaticPool connection. Kept as executable documentation; the real "
        "enforcement was verified live against rpg-postgres with two "
        "genuinely independent connections — see the Stage 6 report."
    )
)
async def test_concurrent_identical_battle_requests_grant_rewards_exactly_once(client, db_session, bot_token):
    from tests.conftest import TestSessionLocal
    from tests.factories import get_user_by_telegram_id

    enemy = await create_enemy_template(
        db_session, name="Слабый враг", level=1, hp=1, attack=1, defense=0, speed=1, reward_xp=15, reward_coins=10
    )
    hero_id, headers = await _make_hero(client, db_session, 9013, bot_token, level=1)
    await db_session.commit()

    user = await get_user_by_telegram_id(db_session, 9013)
    user_id, enemy_id = user.id, enemy.id

    async def attempt() -> str:
        async with TestSessionLocal() as session:
            from app.models.user import User as UserModel
            from app.services.battle_service import start_battle
            from app.services.hero_service import get_active_hero

            u = await session.get(UserModel, user_id)
            hero = await get_active_hero(session, u)
            try:
                await start_battle(session, u, hero, enemy_id, "concurrent-battle-key")
                return "ok"
            except Exception as exc:
                return type(exc).__name__

    results = await asyncio.gather(attempt(), attempt())
    assert results == ["ok", "ok"]  # idempotency replay, not an error, on the loser

    async with TestSessionLocal() as session:
        from sqlalchemy import select

        from app.models.battle import Battle

        battles = (await session.execute(select(Battle).where(Battle.user_id == user_id))).scalars().all()
        assert len(battles) == 1

        refreshed = await get_user_by_telegram_id(session, 9013)
        assert refreshed.balance == 10  # credited exactly once
