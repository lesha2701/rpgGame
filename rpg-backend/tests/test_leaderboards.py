from tests.factories import (
    create_class,
    create_enemy_template,
    create_hero_template,
    create_race,
    get_user_by_telegram_id,
    set_balance,
    set_hero_level,
)
from tests.utils import telegram_headers


async def _register(client, telegram_id, bot_token):
    headers = telegram_headers(telegram_id, bot_token)
    resp = await client.post("/api/v1/auth/session", headers=headers)
    assert resp.status_code == 200
    return headers


async def _make_hero(client, db_session, telegram_id, bot_token, level: int = 1, xp: int = 0) -> dict:
    headers = await _register(client, telegram_id, bot_token)
    race = await create_race(db_session, code=f"lb-race-{telegram_id}")
    char_class = await create_class(db_session, code=f"lb-class-{telegram_id}", base_crit_chance=0.0)
    template = await create_hero_template(db_session, name=f"LBHero{telegram_id}", race=race, char_class=char_class)
    await db_session.commit()

    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id})
    assert resp.status_code == 201
    hero_id = resp.json()["id"]

    if level != 1 or xp:
        await set_hero_level(db_session, hero_id, level)
        from app.models.user_hero import UserHero

        row = await db_session.get(UserHero, hero_id)
        row.xp = xp
        db_session.add(row)
        await db_session.commit()

    user = await get_user_by_telegram_id(db_session, telegram_id)
    return {"telegram_id": telegram_id, "headers": headers, "hero_id": hero_id, "user_id": user.id}


async def _win_battles(client, db_session, headers, count: int) -> None:
    enemy = await create_enemy_template(db_session, name=f"LBTarget-{id(object())}", hp=1, attack=1, defense=0, speed=1)
    await db_session.commit()
    for _ in range(count):
        resp = await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id})
        assert resp.status_code == 201
        assert resp.json()["result"] == "won"


async def _lose_battles(client, db_session, headers, count: int) -> None:
    enemy = await create_enemy_template(
        db_session, name=f"LBBoss-{id(object())}", hp=100000, attack=99999, defense=0, speed=99
    )
    await db_session.commit()
    for _ in range(count):
        resp = await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id})
        assert resp.status_code == 201
        assert resp.json()["result"] == "lost"


# --- level leaderboard --------------------------------------------------------

async def test_level_leaderboard_sorts_by_level_then_xp_then_id(client, db_session, bot_token):
    low = await _make_hero(client, db_session, 50001, bot_token, level=1)
    high_more_xp = await _make_hero(client, db_session, 50002, bot_token, level=5, xp=100)
    high_less_xp = await _make_hero(client, db_session, 50003, bot_token, level=5, xp=10)

    resp = await client.get("/api/v1/leaderboards/level", headers=low["headers"])
    assert resp.status_code == 200
    body = resp.json()
    ids_in_order = [e["user_id"] for e in body["entries"]]
    assert ids_in_order.index(high_more_xp["user_id"]) < ids_in_order.index(high_less_xp["user_id"])
    assert ids_in_order.index(high_less_xp["user_id"]) < ids_in_order.index(low["user_id"])
    for entry in body["entries"]:
        assert entry["rank"] >= 1


async def test_level_leaderboard_id_tiebreak(client, db_session, bot_token):
    first = await _make_hero(client, db_session, 50004, bot_token, level=3, xp=0)
    second = await _make_hero(client, db_session, 50005, bot_token, level=3, xp=0)

    resp = await client.get("/api/v1/leaderboards/level", headers=first["headers"])
    entries = {e["user_id"]: e["rank"] for e in resp.json()["entries"]}
    assert entries[first["user_id"]] < entries[second["user_id"]]


async def test_level_leaderboard_pagination(client, db_session, bot_token):
    users = []
    for i in range(5):
        u = await _make_hero(client, db_session, 50100 + i, bot_token, level=10 - i)
        users.append(u)

    page1 = await client.get("/api/v1/leaderboards/level?limit=2&offset=0", headers=users[0]["headers"])
    page2 = await client.get("/api/v1/leaderboards/level?limit=2&offset=2", headers=users[0]["headers"])
    assert len(page1.json()["entries"]) == 2
    assert len(page2.json()["entries"]) == 2
    assert page1.json()["entries"][0]["user_id"] != page2.json()["entries"][0]["user_id"]
    assert page1.json()["total"] >= 5
    assert page1.json()["limit"] == 2
    assert page1.json()["offset"] == 0


async def test_leaderboard_pagination_bounds_rejected(client, db_session, bot_token):
    headers = await _register(client, 50200, bot_token)
    too_big = await client.get("/api/v1/leaderboards/level?limit=101", headers=headers)
    assert too_big.status_code == 422
    zero = await client.get("/api/v1/leaderboards/level?limit=0", headers=headers)
    assert zero.status_code == 422
    negative_offset = await client.get("/api/v1/leaderboards/level?offset=-1", headers=headers)
    assert negative_offset.status_code == 422


async def test_leaderboard_my_rank_and_my_value(client, db_session, bot_token):
    a = await _make_hero(client, db_session, 50300, bot_token, level=7)
    b = await _make_hero(client, db_session, 50301, bot_token, level=3)

    resp = await client.get("/api/v1/leaderboards/level", headers=a["headers"])
    body = resp.json()
    assert body["my_value"] == 7
    assert body["my_rank"] is not None

    resp_b = await client.get("/api/v1/leaderboards/level", headers=b["headers"])
    assert resp_b.json()["my_value"] == 3


async def test_invalid_leaderboard_type_is_422(client, db_session, bot_token):
    headers = await _register(client, 50400, bot_token)
    resp = await client.get("/api/v1/leaderboards/not_a_real_type", headers=headers)
    assert resp.status_code == 422


# --- pve wins leaderboard ------------------------------------------------------

async def test_pve_wins_leaderboard_counts_wins_not_losses(client, db_session, bot_token):
    winner = await _make_hero(client, db_session, 50500, bot_token)
    loser_only = await _make_hero(client, db_session, 50501, bot_token)

    await _win_battles(client, db_session, winner["headers"], 3)
    await _lose_battles(client, db_session, loser_only["headers"], 2)

    resp = await client.get("/api/v1/leaderboards/pve_wins", headers=winner["headers"])
    body = resp.json()
    winner_entry = next(e for e in body["entries"] if e["user_id"] == winner["user_id"])
    assert winner_entry["value"] == 3

    loser_entry = next((e for e in body["entries"] if e["user_id"] == loser_only["user_id"]), None)
    assert loser_entry is None


async def test_pve_wins_leaderboard_my_value_zero_when_no_wins(client, db_session, bot_token):
    user = await _make_hero(client, db_session, 50502, bot_token)
    resp = await client.get("/api/v1/leaderboards/pve_wins", headers=user["headers"])
    body = resp.json()
    assert body["my_value"] == 0
    assert body["my_rank"] is None


# --- arena wins leaderboard -----------------------------------------------------

async def test_arena_wins_leaderboard_counts_winner_only(client, db_session, bot_token):
    race = await create_race(db_session, code="lb-arena-race")
    strong = await create_class(
        db_session, code="lb-arena-strong", base_attack=1000, base_defense=0, base_hp=1000,
        base_speed=20, base_crit_chance=0.0,
    )
    weak = await create_class(
        db_session, code="lb-arena-weak", base_attack=1, base_defense=0, base_hp=1, base_speed=1,
        base_crit_chance=0.0,
    )
    template_a = await create_hero_template(db_session, name="LBStrong", race=race, char_class=strong)
    template_b = await create_hero_template(db_session, name="LBWeak", race=race, char_class=weak)
    await db_session.commit()

    headers_a = await _register(client, 50600, bot_token)
    resp_a = await client.post("/api/v1/heroes", headers=headers_a, json={"hero_template_id": template_a.id})
    assert resp_a.status_code == 201
    user_a = await get_user_by_telegram_id(db_session, 50600)

    headers_b = await _register(client, 50601, bot_token)
    resp_b = await client.post("/api/v1/heroes", headers=headers_b, json={"hero_template_id": template_b.id})
    assert resp_b.status_code == 201
    user_b = await get_user_by_telegram_id(db_session, 50601)

    match = await client.post("/api/v1/arena/matches", headers=headers_a, json={"opponent_user_id": user_b.id})
    match_id = match.json()["id"]
    await client.post(f"/api/v1/arena/matches/{match_id}/action", headers=headers_a, json={"round": 1, "action_type": "basic_attack"})
    await client.post(f"/api/v1/arena/matches/{match_id}/action", headers=headers_b, json={"round": 1, "action_type": "basic_attack"})

    resp = await client.get("/api/v1/leaderboards/arena_wins", headers=headers_a)
    body = resp.json()
    winner_entry = next(e for e in body["entries"] if e["user_id"] == user_a.id)
    assert winner_entry["value"] == 1
    loser_entry = next((e for e in body["entries"] if e["user_id"] == user_b.id), None)
    assert loser_entry is None


async def test_arena_wins_leaderboard_empty_when_no_matches_finished(client, db_session, bot_token):
    user = await _make_hero(client, db_session, 50602, bot_token)
    resp = await client.get("/api/v1/leaderboards/arena_wins", headers=user["headers"])
    body = resp.json()
    assert body["entries"] == []
    assert body["total"] == 0
    assert body["my_rank"] is None
    assert body["my_value"] == 0


# --- coins leaderboard -----------------------------------------------------------

async def test_coins_leaderboard_sorts_by_current_balance(client, db_session, bot_token):
    rich = await _register(client, 50700, bot_token)
    poor = await _register(client, 50701, bot_token)
    user_rich = await get_user_by_telegram_id(db_session, 50700)
    user_poor = await get_user_by_telegram_id(db_session, 50701)
    await set_balance(db_session, user_rich, 5000)
    await set_balance(db_session, user_poor, 10)

    resp = await client.get("/api/v1/leaderboards/coins", headers=rich)
    body = resp.json()
    ids_in_order = [e["user_id"] for e in body["entries"]]
    assert ids_in_order.index(user_rich.id) < ids_in_order.index(user_poor.id)
    rich_entry = next(e for e in body["entries"] if e["user_id"] == user_rich.id)
    assert rich_entry["value"] == 5000


async def test_coins_leaderboard_reflects_balance_change_immediately(client, db_session, bot_token):
    headers = await _register(client, 50702, bot_token)
    user = await get_user_by_telegram_id(db_session, 50702)
    await set_balance(db_session, user, 100)

    resp1 = await client.get("/api/v1/leaderboards/coins", headers=headers)
    assert resp1.json()["my_value"] == 100

    await set_balance(db_session, user, 999)
    resp2 = await client.get("/api/v1/leaderboards/coins", headers=headers)
    assert resp2.json()["my_value"] == 999


# --- security: leaderboard never leaks telegram_id ---------------------------

async def test_leaderboard_entries_do_not_leak_telegram_id(client, db_session, bot_token):
    user = await _make_hero(client, db_session, 50800, bot_token)
    resp = await client.get("/api/v1/leaderboards/level", headers=user["headers"])
    body = resp.json()
    for entry in body["entries"]:
        assert "telegram_id" not in entry
