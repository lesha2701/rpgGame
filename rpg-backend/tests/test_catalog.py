from tests.factories import create_class, create_hero_template, create_race
from tests.utils import telegram_headers


async def test_list_races(client, db_session, bot_token):
    await create_race(db_session, code="human", name="Человек")
    await create_race(db_session, code="orc", name="Орк")
    await db_session.commit()

    resp = await client.get("/api/v1/races", headers=telegram_headers(1001, bot_token))
    assert resp.status_code == 200
    codes = {r["code"] for r in resp.json()}
    assert codes == {"human", "orc"}


async def test_inactive_race_is_hidden(client, db_session, bot_token):
    race = await create_race(db_session, code="hidden", name="Скрытая раса")
    race.is_active = False
    db_session.add(race)
    await db_session.commit()

    resp = await client.get("/api/v1/races", headers=telegram_headers(1002, bot_token))
    codes = {r["code"] for r in resp.json()}
    assert "hidden" not in codes


async def test_list_classes_exposes_base_stats(client, db_session, bot_token):
    await create_class(db_session, code="warrior", name="Воин", base_hp=120)
    await db_session.commit()

    resp = await client.get("/api/v1/classes", headers=telegram_headers(1003, bot_token))
    assert resp.status_code == 200
    warrior = next(c for c in resp.json() if c["code"] == "warrior")
    assert warrior["base_hp"] == 120


async def test_list_hero_templates_includes_race_and_class(client, db_session, bot_token):
    race = await create_race(db_session, code="human", name="Человек")
    char_class = await create_class(db_session, code="warrior", name="Воин")
    await create_hero_template(db_session, name="Алдрик", race=race, char_class=char_class)
    await db_session.commit()

    resp = await client.get("/api/v1/hero-templates", headers=telegram_headers(1004, bot_token))
    assert resp.status_code == 200
    template = resp.json()[0]
    assert template["name"] == "Алдрик"
    assert template["race"]["code"] == "human"
    assert template["character_class"]["code"] == "warrior"
