import asyncio

import pytest
from tests.factories import create_class, create_hero_template, create_skill_definition, set_hero_level
from tests.utils import telegram_headers

from app.services.hero_service import grant_xp
from app.services.progression import xp_to_next_level
from app.services.skill_progression import MAX_SKILL_LEVEL
from app.services.skill_service import get_skill_budget, upgrade_skill


async def _make_hero_with_skills(db_session, telegram_id: int):
    """3 skills on one class, staggered unlock levels — mirrors the seed
    data's shape (1 / 5 / 15) without depending on the actual seed content."""
    char_class = await create_class(db_session, code=f"cls{telegram_id}", name="ТестКласс")
    skill1 = await create_skill_definition(db_session, char_class, code="s1", name="Навык 1", required_hero_level=1)
    skill2 = await create_skill_definition(db_session, char_class, code="s2", name="Навык 2", required_hero_level=5)
    skill3 = await create_skill_definition(db_session, char_class, code="s3", name="Навык 3", required_hero_level=15)
    template = await create_hero_template(db_session, name=f"Герой{telegram_id}", char_class=char_class)
    await db_session.commit()
    return char_class, (skill1, skill2, skill3), template


async def _create_hero_via_api(client, db_session, template, telegram_id, bot_token):
    headers = telegram_headers(telegram_id, bot_token)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id, "name": "Герой"})
    assert resp.status_code == 201
    return resp.json()["id"], headers


# --- unlock requirements: first from the start, later ones gated by level -----

async def test_first_skill_is_unlocked_from_level_1(client, db_session, bot_token):
    _cls, (s1, s2, s3), template = await _make_hero_with_skills(db_session, 5001)
    _hero_id, headers = await _create_hero_via_api(client, db_session, template, 5001, bot_token)

    resp = await client.get("/api/v1/heroes/me/skills/available", headers=headers)
    assert resp.status_code == 200
    by_code = {s["skill_definition"]["code"]: s for s in resp.json()["skills"]}
    assert by_code["s1"]["is_unlocked"] is True
    assert by_code["s2"]["is_unlocked"] is False
    assert by_code["s3"]["is_unlocked"] is False


async def test_owned_skills_list_is_empty_before_learning_anything(client, db_session, bot_token):
    _cls, _skills, template = await _make_hero_with_skills(db_session, 5002)
    _hero_id, headers = await _create_hero_via_api(client, db_session, template, 5002, bot_token)

    resp = await client.get("/api/v1/heroes/me/skills", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


# --- learning / upgrading -------------------------------------------------

async def test_upgrading_an_unlearned_skill_learns_it_at_level_1(client, db_session, bot_token):
    _cls, (s1, _s2, _s3), template = await _make_hero_with_skills(db_session, 5003)
    _hero_id, headers = await _create_hero_via_api(client, db_session, template, 5003, bot_token)

    resp = await client.post(f"/api/v1/heroes/me/skills/{s1.id}/upgrade", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["level"] == 1
    assert body["skill_definition"]["code"] == "s1"
    assert body["power"] == float(s1.base_power)  # level 1 == base power exactly


async def test_second_upgrade_raises_level_to_2(client, db_session, bot_token):
    """Needs 2 skill points, so give the hero a level-2 worth of XP first."""
    _cls, (s1, _s2, _s3), template = await _make_hero_with_skills(db_session, 5004)
    hero_id, headers = await _create_hero_via_api(client, db_session, template, 5004, bot_token)
    await grant_xp(db_session, hero_id, xp_to_next_level(1))  # -> level 2, budget 2
    await db_session.commit()

    await client.post(f"/api/v1/heroes/me/skills/{s1.id}/upgrade", headers=headers)
    resp = await client.post(f"/api/v1/heroes/me/skills/{s1.id}/upgrade", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["level"] == 2

    listed = await client.get("/api/v1/heroes/me/skills", headers=headers)
    assert len(listed.json()) == 1
    assert listed.json()[0]["level"] == 2


# --- level-too-low is rejected, then works once the hero levels up -----------

async def test_cannot_learn_a_skill_below_its_required_hero_level(client, db_session, bot_token):
    _cls, (_s1, s2, _s3), template = await _make_hero_with_skills(db_session, 5005)
    _hero_id, headers = await _create_hero_via_api(client, db_session, template, 5005, bot_token)

    resp = await client.post(f"/api/v1/heroes/me/skills/{s2.id}/upgrade", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_skill_becomes_learnable_after_reaching_its_required_level(client, db_session, bot_token):
    _cls, (_s1, s2, _s3), template = await _make_hero_with_skills(db_session, 5006)
    hero_id, headers = await _create_hero_via_api(client, db_session, template, 5006, bot_token)
    await set_hero_level(db_session, hero_id, 5)
    await db_session.commit()

    resp = await client.post(f"/api/v1/heroes/me/skills/{s2.id}/upgrade", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["level"] == 1


# --- max skill level ---------------------------------------------------------

async def test_cannot_upgrade_a_skill_past_level_10(db_session, bot_token):
    """Drives the skill straight to level 10 via the service (bypassing the
    budget check by granting enough hero levels first), then asserts the
    11th attempt is rejected regardless of available budget."""
    char_class = await create_class(db_session, code="capclass", name="КапКласс")
    skill = await create_skill_definition(db_session, char_class, code="cap", name="Капскилл", required_hero_level=1)
    template = await create_hero_template(db_session, name="КапГерой", char_class=char_class)
    await db_session.commit()

    from app.services.hero_service import create_hero

    # Bypass the HTTP layer here: register the user directly then create the
    # hero via the service, so we can freely push hero level past 100 checks
    # without needing 10 separate registered-XP round trips.
    from app.models.user import User

    user = User(telegram_id=590001)
    db_session.add(user)
    await db_session.flush()
    hero = await create_hero(db_session, user.id, template.id, "Герой")
    await set_hero_level(db_session, hero.id, 100)  # budget 100, plenty for 10 upgrades
    await db_session.commit()

    for expected_level in range(1, MAX_SKILL_LEVEL + 1):
        result = await upgrade_skill(db_session, hero.id, skill.id)
        assert result.level == expected_level

    try:
        await upgrade_skill(db_session, hero.id, skill.id)
        assert False, "expected ConflictError at max level"
    except Exception as exc:
        assert type(exc).__name__ == "ConflictError"


# --- insufficient resources ---------------------------------------------------

async def test_insufficient_budget_blocks_a_second_upgrade(client, db_session, bot_token):
    """Hero stays at level 1 -> budget 1. Learning s1 spends the only point;
    trying to raise it to level 2 has nothing left to spend."""
    _cls, (s1, _s2, _s3), template = await _make_hero_with_skills(db_session, 5007)
    _hero_id, headers = await _create_hero_via_api(client, db_session, template, 5007, bot_token)

    first = await client.post(f"/api/v1/heroes/me/skills/{s1.id}/upgrade", headers=headers)
    assert first.status_code == 200

    second = await client.post(f"/api/v1/heroes/me/skills/{s1.id}/upgrade", headers=headers)
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "insufficient_resources"


async def test_leveling_up_grants_more_budget_for_further_upgrades(client, db_session, bot_token):
    _cls, (s1, _s2, _s3), template = await _make_hero_with_skills(db_session, 5008)
    hero_id, headers = await _create_hero_via_api(client, db_session, template, 5008, bot_token)

    await client.post(f"/api/v1/heroes/me/skills/{s1.id}/upgrade", headers=headers)  # spends the level-1 budget
    blocked = await client.post(f"/api/v1/heroes/me/skills/{s1.id}/upgrade", headers=headers)
    assert blocked.status_code == 400

    await grant_xp(db_session, hero_id, xp_to_next_level(1))  # -> level 2, +1 budget
    await db_session.commit()
    unblocked = await client.post(f"/api/v1/heroes/me/skills/{s1.id}/upgrade", headers=headers)
    assert unblocked.status_code == 200
    assert unblocked.json()["level"] == 2


# --- unknown / wrong-class skill ids -------------------------------------------

async def test_unknown_skill_definition_is_404(client, db_session, bot_token):
    _cls, _skills, template = await _make_hero_with_skills(db_session, 5009)
    _hero_id, headers = await _create_hero_via_api(client, db_session, template, 5009, bot_token)

    resp = await client.post("/api/v1/heroes/me/skills/999999/upgrade", headers=headers)
    assert resp.status_code == 404


async def test_skill_from_a_different_class_is_404(client, db_session, bot_token):
    _cls, _skills, template = await _make_hero_with_skills(db_session, 5010)
    _hero_id, headers = await _create_hero_via_api(client, db_session, template, 5010, bot_token)

    other_class = await create_class(db_session, code="otherclass5010", name="ДругойКласс")
    foreign_skill = await create_skill_definition(db_session, other_class, code="foreign", name="Чужой навык")
    await db_session.commit()

    resp = await client.post(f"/api/v1/heroes/me/skills/{foreign_skill.id}/upgrade", headers=headers)
    assert resp.status_code == 404


# --- concurrent upgrades must not overspend the shared budget -----------------

@pytest.mark.skip(
    reason=(
        "SQLite's dialect silently no-ops with_for_update() (single shared "
        "StaticPool connection, no real row locking) — same documented "
        "limitation as the football backend (CLAUDE.md: 'Row-level locking "
        "is not exercised by the SQLite test DB — verify locking-dependent "
        "changes manually against real Postgres'). Kept here, skipped, as "
        "executable documentation of what the lock is protecting against; "
        "the real enforcement was verified live against rpg-postgres — see "
        "the Stage 3 report for the transcript. Un-skip if this suite ever "
        "moves to a Postgres-backed test DB."
    )
)
async def test_concurrent_upgrades_never_overspend_the_shared_budget(client, db_session, bot_token):
    """Two skills, both unlocked at level 1, hero has exactly 1 skill point.
    Firing both upgrades concurrently must result in exactly one success —
    the row lock on the hero (services.hero_service.lock_hero_for_update)
    is what serializes the budget check-then-spend across *different*
    skills on the same hero, not just the per-skill unique constraint."""
    from tests.conftest import TestSessionLocal

    char_class = await create_class(db_session, code="raceclass", name="Гонка")
    skill_a = await create_skill_definition(db_session, char_class, code="race_a", name="Навык A", required_hero_level=1)
    skill_b = await create_skill_definition(db_session, char_class, code="race_b", name="Навык B", required_hero_level=1)
    template = await create_hero_template(db_session, name="Гонщик", char_class=char_class)
    await db_session.commit()

    hero_id, _headers = await _create_hero_via_api(client, db_session, template, 5011, bot_token)

    async def attempt(skill_id: int) -> str:
        async with TestSessionLocal() as session:
            try:
                await upgrade_skill(session, hero_id, skill_id)
                return "ok"
            except Exception as exc:
                return type(exc).__name__

    results = await asyncio.gather(attempt(skill_a.id), attempt(skill_b.id))
    assert sorted(results) == ["InsufficientResourcesError", "ok"]

    async with TestSessionLocal() as session:
        from app.models.user_hero import UserHero

        hero = await session.get(UserHero, hero_id)
        assert hero is not None
        _total, spent = await get_skill_budget(session, hero)
        assert spent == 1  # exactly one of the two upgrades actually landed
