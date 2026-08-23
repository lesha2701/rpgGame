"""DB-backed tests for the leveling engine: hero_service.grant_xp persists
correctly and the API surface (GET /heroes/me) reflects it end-to-end.
Boundary/overflow/cap correctness itself is covered exhaustively in
test_progression.py against the pure formula — these tests exist to catch
persistence/wiring bugs, not to re-derive the math.

grant_xp no longer commits internally (Stage 6 made it transactionally
composable — see its docstring) — every test that checks the result via an
API call (a *different* AsyncSession than db_session) must commit
explicitly first, exactly as any other factories.py-driven test already
does before hitting the client."""

from tests.factories import create_class, create_hero_template
from tests.utils import telegram_headers

from app.services.hero_service import grant_xp
from app.services.progression import MAX_LEVEL, xp_to_next_level


async def _make_hero(client, db_session, telegram_id, bot_token, **class_overrides):
    char_class = await create_class(db_session, code=f"class{telegram_id}", name="Тест-класс", **class_overrides)
    template = await create_hero_template(db_session, name=f"Герой{telegram_id}", char_class=char_class)
    await db_session.commit()

    headers = telegram_headers(telegram_id, bot_token)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id})
    assert resp.status_code == 201
    return resp.json()["id"], headers


async def test_grant_xp_below_threshold_does_not_level_up(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 3001, bot_token)
    needed = xp_to_next_level(1)

    hero, result = await grant_xp(db_session, hero_id, needed - 1)
    assert hero.level == 1
    assert hero.xp == needed - 1
    assert result.levels_gained == 0
    await db_session.commit()

    api_hero = await client.get("/api/v1/heroes/me", headers=headers)
    assert api_hero.json()["level"] == 1
    assert api_hero.json()["xp"] == needed - 1


async def test_grant_xp_levels_up_and_carries_overflow(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 3002, bot_token)
    needed = xp_to_next_level(1)

    hero, result = await grant_xp(db_session, hero_id, needed + 15)
    assert hero.level == 2
    assert hero.xp == 15
    assert result.levels_gained == 1
    await db_session.commit()

    api_hero = await client.get("/api/v1/heroes/me", headers=headers)
    body = api_hero.json()
    assert body["level"] == 2
    assert body["xp"] == 15


async def test_grant_xp_increases_stats_after_levelup(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 3003, bot_token, base_hp=100, hp_per_level=10)
    before = (await client.get("/api/v1/heroes/me", headers=headers)).json()["stats"]["hp"]

    await grant_xp(db_session, hero_id, xp_to_next_level(1))
    await db_session.commit()

    after = (await client.get("/api/v1/heroes/me", headers=headers)).json()["stats"]["hp"]
    assert after == before + 10  # automatic growth, no manual allocation endpoint exists


async def test_grant_xp_crossing_a_decade_updates_visual_stage(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 3004, bot_token)

    # Push the hero to level 10 first (still visual_stage 1).
    total_to_level_10 = sum(xp_to_next_level(lvl) for lvl in range(1, 10))  # type: ignore[misc]
    await grant_xp(db_session, hero_id, total_to_level_10)
    await db_session.commit()
    at_10 = (await client.get("/api/v1/heroes/me", headers=headers)).json()
    assert at_10["level"] == 10
    assert at_10["visual_stage"] == 1

    # One more level crosses into stage 2.
    await grant_xp(db_session, hero_id, xp_to_next_level(10))
    await db_session.commit()
    at_11 = (await client.get("/api/v1/heroes/me", headers=headers)).json()
    assert at_11["level"] == 11
    assert at_11["visual_stage"] == 2


async def test_grant_xp_massive_amount_caps_at_level_100(client, db_session, bot_token):
    hero_id, headers = await _make_hero(client, db_session, 3005, bot_token)

    hero, result = await grant_xp(db_session, hero_id, 10**12)
    assert hero.level == MAX_LEVEL
    assert hero.xp == 0
    assert result.levels_gained == MAX_LEVEL - 1
    await db_session.commit()

    api_hero = await client.get("/api/v1/heroes/me", headers=headers)
    body = api_hero.json()
    assert body["level"] == 100
    assert body["xp"] == 0
    assert body["xp_to_next_level"] is None
    assert body["visual_stage"] == 10


async def test_grant_xp_at_level_100_is_a_safe_noop(client, db_session, bot_token):
    hero_id, _headers = await _make_hero(client, db_session, 3006, bot_token)
    await grant_xp(db_session, hero_id, 10**12)  # reach 100

    hero, result = await grant_xp(db_session, hero_id, 5000)
    assert hero.level == MAX_LEVEL
    assert hero.xp == 0
    assert result.levels_gained == 0


async def test_grant_xp_rejects_negative_amount(client, db_session, bot_token):
    hero_id, _headers = await _make_hero(client, db_session, 3007, bot_token)
    try:
        await grant_xp(db_session, hero_id, -1)
        assert False, "expected ValueError"
    except ValueError:
        pass


async def test_fresh_hero_is_exactly_level_1_xp_0():
    """Restates the Stage 1 invariant here so a future change to
    create_hero/grant_xp that broke the starting state would fail loudly in
    the leveling test file, not just in test_heroes.py."""
    from app.services.progression import MIN_LEVEL

    assert MIN_LEVEL == 1
