from tests.factories import create_hero_template
from tests.utils import telegram_headers


async def test_no_hero_yet_returns_404(client, bot_token):
    resp = await client.get("/api/v1/heroes/me", headers=telegram_headers(2001, bot_token))
    assert resp.status_code == 404


async def test_create_hero_starts_at_level_1_xp_0(client, db_session, bot_token):
    template = await create_hero_template(db_session, name="Алдрик")
    await db_session.commit()

    headers = telegram_headers(2002, bot_token)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id, "name": "Герой"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["level"] == 1
    assert body["xp"] == 0
    assert body["visual_stage"] == 1
    assert body["hero_template"]["name"] == "Алдрик"
    assert body["stats"]["hp"] > 0


async def test_created_hero_becomes_the_active_hero(client, db_session, bot_token):
    template = await create_hero_template(db_session, name="Алдрик")
    await db_session.commit()

    headers = telegram_headers(2003, bot_token)
    await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id, "name": "Герой"})

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["active_hero"]["hero_template"]["name"] == "Алдрик"

    hero = await client.get("/api/v1/heroes/me", headers=headers)
    assert hero.status_code == 200
    assert hero.json()["hero_template"]["name"] == "Алдрик"


async def test_cannot_create_a_second_active_hero(client, db_session, bot_token):
    template = await create_hero_template(db_session, name="Алдрик")
    await db_session.commit()

    headers = telegram_headers(2004, bot_token)
    first = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id, "name": "Герой"})
    assert first.status_code == 201

    second = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id, "name": "Герой"})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


async def test_creating_hero_from_unknown_template_404s(client, bot_token):
    headers = telegram_headers(2005, bot_token)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": 999999, "name": "Герой"})
    assert resp.status_code == 404


async def test_hero_name_is_required(client, db_session, bot_token):
    template = await create_hero_template(db_session, name="Алдрик")
    await db_session.commit()

    headers = telegram_headers(2006, bot_token)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id})
    assert resp.status_code == 422


async def test_hero_name_must_not_be_blank(client, db_session, bot_token):
    template = await create_hero_template(db_session, name="Алдрик")
    await db_session.commit()

    headers = telegram_headers(2007, bot_token)
    resp = await client.post(
        "/api/v1/heroes", headers=headers, json={"hero_template_id": template.id, "name": "   "}
    )
    assert resp.status_code == 422


async def test_hero_name_is_own_and_distinct_from_template_name(client, db_session, bot_token):
    """Two players picking the same template must still get distinct hero
    identities — this is what makes leaderboards show real player names
    instead of every user of a template looking identical."""
    template = await create_hero_template(db_session, name="Алдрик")
    await db_session.commit()

    headers_a = telegram_headers(2008, bot_token)
    resp_a = await client.post(
        "/api/v1/heroes", headers=headers_a, json={"hero_template_id": template.id, "name": "Громобой"}
    )
    assert resp_a.status_code == 201
    assert resp_a.json()["name"] == "Громобой"
    assert resp_a.json()["hero_template"]["name"] == "Алдрик"

    headers_b = telegram_headers(2009, bot_token)
    resp_b = await client.post(
        "/api/v1/heroes", headers=headers_b, json={"hero_template_id": template.id, "name": "Тенеход"}
    )
    assert resp_b.status_code == 201
    assert resp_b.json()["name"] == "Тенеход"


async def test_stats_scale_with_level(db_session):
    """Not exercised through the API in Stage 1 (nothing grants XP yet) —
    this directly checks the progression formula that hero_to_out uses,
    so Stage 2's level-up trigger has a known-correct formula to call."""
    from tests.factories import create_class

    from app.services.progression import compute_stats

    char_class = await create_class(
        db_session, code="warrior2", name="Воин2", base_hp=100, hp_per_level=10, attack_per_level=2
    )
    await db_session.commit()

    level_1 = compute_stats(char_class, 1)
    level_11 = compute_stats(char_class, 11)
    assert level_1.hp == 100
    assert level_11.hp == 200  # 100 + 10 levels gained * 10 hp/level
    assert level_11.attack == level_1.attack + 20
