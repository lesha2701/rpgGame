import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from tests.factories import create_class, create_hero_template, create_race, create_skill_definition, get_user_by_telegram_id, set_hero_level
from tests.utils import telegram_headers

from app.models.arena_match import ArenaMatch
from app.models.enums import SkillType


async def _register_and_create_hero(client, telegram_id, bot_token, hero_template_id):
    headers = telegram_headers(telegram_id, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": hero_template_id, "name": "Герой"})
    assert resp.status_code == 201
    return resp.json()["id"], headers


async def _make_two_heroes(
    client, db_session, bot_token, telegram_a=20001, telegram_b=20002, template_a=None, template_b=None
):
    race = None
    if template_a is None or template_b is None:
        race = await create_race(db_session, code=f"race-{telegram_a}-{telegram_b}")
    if template_a is None:
        # base_crit_chance=0.0: DEFAULT_CLASS_STATS' 0.05 would make a
        # "perfectly symmetric" damage exchange non-deterministic (a random
        # crit on one side but not the other breaks an exact-tie
        # assumption over many rounds) — tests that need real crit
        # behavior create their own class with it turned back on.
        class_a = await create_class(db_session, code=f"cls-a-{telegram_a}", name="ClassA", base_crit_chance=0.0)
        template_a = await create_hero_template(db_session, name=f"HeroA-{telegram_a}", race=race, char_class=class_a)
    if template_b is None:
        class_b = await create_class(db_session, code=f"cls-b-{telegram_b}", name="ClassB", base_crit_chance=0.0)
        template_b = await create_hero_template(db_session, name=f"HeroB-{telegram_b}", race=race, char_class=class_b)
    await db_session.commit()

    hero_a_id, headers_a = await _register_and_create_hero(client, telegram_a, bot_token, template_a.id)
    hero_b_id, headers_b = await _register_and_create_hero(client, telegram_b, bot_token, template_b.id)
    user_a = await get_user_by_telegram_id(db_session, telegram_a)
    user_b = await get_user_by_telegram_id(db_session, telegram_b)
    return {
        "hero_a_id": hero_a_id, "headers_a": headers_a, "user_a_id": user_a.id, "telegram_a": telegram_a,
        "hero_b_id": hero_b_id, "headers_b": headers_b, "user_b_id": user_b.id, "telegram_b": telegram_b,
        "race": race,
    }


async def _make_lopsided_heroes(client, db_session, bot_token, telegram_a=20101, telegram_b=20102):
    """player_a one-shots player_b on the very first exchange — deterministic
    win/loss tests don't need to grind through many rounds."""
    race = await create_race(db_session, code=f"race-{telegram_a}-{telegram_b}")
    strong = await create_class(
        db_session, code=f"strong-{telegram_a}", name="Strong",
        base_attack=1000, base_defense=0, base_hp=1000, base_speed=20, base_crit_chance=0.0,
    )
    weak = await create_class(
        db_session, code=f"weak-{telegram_b}", name="Weak",
        base_attack=1, base_defense=0, base_hp=1, base_speed=1, base_crit_chance=0.0,
    )
    template_a = await create_hero_template(db_session, name="StrongHero", race=race, char_class=strong)
    template_b = await create_hero_template(db_session, name="WeakHero", race=race, char_class=weak)
    ctx = await _make_two_heroes(client, db_session, bot_token, telegram_a, telegram_b, template_a, template_b)
    ctx["race"] = race
    return ctx


async def _create_match(client, headers_a, opponent_user_id):
    resp = await client.post("/api/v1/arena/matches", headers=headers_a, json={"opponent_user_id": opponent_user_id})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _submit(client, headers, match_id, round_number, action_type="basic_attack", skill_id=None):
    return await client.post(
        f"/api/v1/arena/matches/{match_id}/action",
        headers=headers,
        json={"round": round_number, "action_type": action_type, "skill_id": skill_id},
    )


async def _force_overdue(db_session, match_id: int) -> None:
    match = await db_session.get(ArenaMatch, match_id)
    match.round_deadline_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.add(match)
    await db_session.commit()


# --- create ------------------------------------------------------------------

async def test_create_match_snapshots_both_heroes_and_starts_running(client, db_session, bot_token):
    ctx = await _make_two_heroes(client, db_session, bot_token, 20001, 20002)
    body = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    assert body["status"] == "running"
    assert body["current_round"] == 1
    assert body["player_a"]["hero_id"] == ctx["hero_a_id"]
    assert body["player_b"]["hero_id"] == ctx["hero_b_id"]
    assert body["player_a"]["current_hp"] == 100
    assert body["player_b"]["current_hp"] == 100
    assert body["player_a"]["has_acted_this_round"] is False


async def test_cannot_challenge_yourself(client, db_session, bot_token):
    ctx = await _make_two_heroes(client, db_session, bot_token, 20003, 20004)
    resp = await client.post(
        "/api/v1/arena/matches", headers=ctx["headers_a"], json={"opponent_user_id": ctx["user_a_id"]}
    )
    assert resp.status_code == 409


async def test_challenging_unknown_user_is_404(client, db_session, bot_token):
    ctx = await _make_two_heroes(client, db_session, bot_token, 20005, 20006)
    resp = await client.post(
        "/api/v1/arena/matches", headers=ctx["headers_a"], json={"opponent_user_id": 999999}
    )
    assert resp.status_code == 404


async def test_challenging_a_user_without_a_hero_is_404(client, db_session, bot_token):
    headers_a = telegram_headers(20007, bot_token)
    await client.post("/api/v1/auth/session", headers=headers_a)
    headers_b = telegram_headers(20008, bot_token)
    await client.post("/api/v1/auth/session", headers=headers_b)
    user_b = await get_user_by_telegram_id(db_session, 20008)

    template = await create_hero_template(db_session, name="OnlyA")
    await db_session.commit()
    resp = await client.post("/api/v1/heroes", headers=headers_a, json={"hero_template_id": template.id, "name": "Герой"})
    assert resp.status_code == 201

    resp = await client.post(
        "/api/v1/arena/matches", headers=headers_a, json={"opponent_user_id": user_b.id}
    )
    assert resp.status_code == 404


async def test_hero_already_in_a_match_cannot_start_another(client, db_session, bot_token):
    ctx1 = await _make_two_heroes(client, db_session, bot_token, 20009, 20010)
    await _create_match(client, ctx1["headers_a"], ctx1["user_b_id"])

    # hero_a challenges a third player while already in a match with b
    headers_c = telegram_headers(20011, bot_token)
    await client.post("/api/v1/auth/session", headers=headers_c)
    template_c = await create_hero_template(db_session, name="HeroC", race=ctx1["race"])
    await db_session.commit()
    await client.post("/api/v1/heroes", headers=headers_c, json={"hero_template_id": template_c.id, "name": "Герой"})
    user_c = await get_user_by_telegram_id(db_session, 20011)

    resp = await client.post(
        "/api/v1/arena/matches", headers=ctx1["headers_a"], json={"opponent_user_id": user_c.id}
    )
    assert resp.status_code == 409


async def test_cannot_challenge_an_opponent_already_in_a_running_match(client, db_session, bot_token):
    ctx1 = await _make_two_heroes(client, db_session, bot_token, 20012, 20013)
    await _create_match(client, ctx1["headers_a"], ctx1["user_b_id"])  # b is now busy

    headers_c = telegram_headers(20014, bot_token)
    await client.post("/api/v1/auth/session", headers=headers_c)
    template_c = await create_hero_template(db_session, name="HeroC2", race=ctx1["race"])
    await db_session.commit()
    await client.post("/api/v1/heroes", headers=headers_c, json={"hero_template_id": template_c.id, "name": "Герой"})

    resp = await client.post(
        "/api/v1/arena/matches", headers=headers_c, json={"opponent_user_id": ctx1["user_b_id"]}
    )
    assert resp.status_code == 409


# --- action flow ---------------------------------------------------------------

async def test_first_action_waits_second_action_resolves_the_round(client, db_session, bot_token):
    ctx = await _make_two_heroes(client, db_session, bot_token, 20015, 20016)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    match_id = match["id"]

    first = await _submit(client, ctx["headers_a"], match_id, 1)
    assert first.status_code == 200
    assert first.json()["player_a"]["has_acted_this_round"] is True
    assert first.json()["current_round"] == 1  # not resolved yet
    assert first.json()["log"] == []

    second = await _submit(client, ctx["headers_b"], match_id, 1)
    assert second.status_code == 200
    body = second.json()
    assert body["current_round"] == 2
    assert len(body["log"]) == 2  # both basic attacks applied
    assert body["player_a"]["has_acted_this_round"] is False  # cleared for the new round
    # DEFAULT_CLASS_STATS: attack=10, defense=10 -> max(1, 0) = 1 damage each
    assert body["player_a"]["current_hp"] == 99
    assert body["player_b"]["current_hp"] == 99


async def test_invalid_skill_is_rejected(client, db_session, bot_token):
    ctx = await _make_two_heroes(client, db_session, bot_token, 20017, 20018)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    resp = await _submit(client, ctx["headers_a"], match["id"], 1, action_type="skill", skill_id=999999)
    assert resp.status_code == 409


async def test_action_from_non_participant_is_404(client, db_session, bot_token):
    ctx = await _make_two_heroes(client, db_session, bot_token, 20019, 20020)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])

    headers_c = telegram_headers(20021, bot_token)
    await client.post("/api/v1/auth/session", headers=headers_c)
    resp = await _submit(client, headers_c, match["id"], 1)
    assert resp.status_code == 404


async def test_unknown_match_action_is_404(client, db_session, bot_token):
    ctx = await _make_two_heroes(client, db_session, bot_token, 20022, 20023)
    resp = await _submit(client, ctx["headers_a"], 999999, 1)
    assert resp.status_code == 404


# --- win / loss / reward --------------------------------------------------------

async def test_winning_grants_reward_losing_grants_nothing(client, db_session, bot_token):
    ctx = await _make_lopsided_heroes(client, db_session, bot_token, 20101, 20102)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    match_id = match["id"]

    await _submit(client, ctx["headers_a"], match_id, 1)
    resp = await _submit(client, ctx["headers_b"], match_id, 1)
    body = resp.json()
    assert body["status"] == "finished"
    assert body["winner_user_id"] == ctx["user_a_id"]
    assert body["reward_xp"] > 0
    assert body["reward_coins"] > 0

    # ARENA_WIN_REWARD_XP (50) exactly equals xp_to_next_level(1) (50), so
    # a fresh level-1 winner levels up to 2 with a 0 remainder rather than
    # showing 50 xp at level 1 — apply_xp_gain's normal carry-over
    # behavior (Stage 2), not anything Arena-specific.
    hero_a = await client.get("/api/v1/heroes/me", headers=ctx["headers_a"])
    assert hero_a.json()["level"] == 2
    assert hero_a.json()["xp"] == 0
    hero_b = await client.get("/api/v1/heroes/me", headers=ctx["headers_b"])
    assert hero_b.json()["level"] == 1
    assert hero_b.json()["xp"] == 0

    wallet_a = await client.get("/api/v1/economy", headers=ctx["headers_a"])
    assert wallet_a.json()["coins"] == body["reward_coins"]
    wallet_b = await client.get("/api/v1/economy", headers=ctx["headers_b"])
    assert wallet_b.json()["coins"] == 0


async def test_finished_match_frees_both_heroes_to_start_new_matches(client, db_session, bot_token):
    ctx = await _make_lopsided_heroes(client, db_session, bot_token, 20103, 20104)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    await _submit(client, ctx["headers_a"], match["id"], 1)
    await _submit(client, ctx["headers_b"], match["id"], 1)

    headers_c = telegram_headers(20105, bot_token)
    await client.post("/api/v1/auth/session", headers=headers_c)
    template_c = await create_hero_template(db_session, name="HeroC3", race=ctx["race"])
    await db_session.commit()
    await client.post("/api/v1/heroes", headers=headers_c, json={"hero_template_id": template_c.id, "name": "Герой"})
    user_c = await get_user_by_telegram_id(db_session, 20105)

    resp = await client.post(
        "/api/v1/arena/matches", headers=ctx["headers_a"], json={"opponent_user_id": user_c.id}
    )
    assert resp.status_code == 201


async def test_round_cap_stalemate_player_a_wins_ties(client, db_session, bot_token):
    ctx = await _make_two_heroes(client, db_session, bot_token, 20106, 20107)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    match_id = match["id"]

    round_number = 1
    body = None
    for _ in range(30):
        await _submit(client, ctx["headers_a"], match_id, round_number)
        resp = await _submit(client, ctx["headers_b"], match_id, round_number)
        body = resp.json()
        round_number += 1

    assert body["status"] == "finished"
    assert body["winner_user_id"] == ctx["user_a_id"]
    assert body["player_a"]["current_hp"] == body["player_b"]["current_hp"]  # genuine tie


# --- idempotency -----------------------------------------------------------------

async def test_duplicate_action_before_resolution_does_not_double_apply(client, db_session, bot_token):
    ctx = await _make_two_heroes(client, db_session, bot_token, 20108, 20109)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    match_id = match["id"]

    first = await _submit(client, ctx["headers_a"], match_id, 1)
    duplicate = await _submit(client, ctx["headers_a"], match_id, 1)
    assert duplicate.status_code == 200
    assert duplicate.json() == first.json()

    resp = await _submit(client, ctx["headers_b"], match_id, 1)
    body = resp.json()
    assert body["current_round"] == 2
    # still exactly one basic attack applied per side, not two from a's side
    assert len(body["log"]) == 2
    assert body["player_a"]["current_hp"] == 99


async def test_retry_after_round_already_resolved_does_not_reapply(client, db_session, bot_token):
    """The exact scenario from the brief: A and B both submit, the round
    resolves, but B's client never saw the response (network timeout) and
    retries the identical request. The retry must not deal damage again,
    advance the round again, or grant a reward again."""
    ctx = await _make_two_heroes(client, db_session, bot_token, 20110, 20111)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    match_id = match["id"]

    await _submit(client, ctx["headers_a"], match_id, 1)
    resolved = await _submit(client, ctx["headers_b"], match_id, 1)
    resolved_body = resolved.json()
    assert resolved_body["current_round"] == 2

    # B's retry — still claims round=1, exactly like a resend of the exact
    # same original request.
    retry = await _submit(client, ctx["headers_b"], match_id, 1)
    assert retry.status_code == 200
    retry_body = retry.json()
    assert retry_body["current_round"] == 2  # unchanged, not advanced again
    assert retry_body["log"] == resolved_body["log"]  # no new entries
    assert retry_body["player_a"]["current_hp"] == resolved_body["player_a"]["current_hp"]
    assert retry_body["player_b"]["current_hp"] == resolved_body["player_b"]["current_hp"]


async def test_retry_after_the_finishing_round_does_not_grant_reward_twice(client, db_session, bot_token):
    ctx = await _make_lopsided_heroes(client, db_session, bot_token, 20112, 20113)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    match_id = match["id"]

    await _submit(client, ctx["headers_a"], match_id, 1)
    finishing = await _submit(client, ctx["headers_b"], match_id, 1)
    assert finishing.json()["status"] == "finished"

    retry = await _submit(client, ctx["headers_b"], match_id, 1)
    assert retry.status_code == 200
    assert retry.json() == finishing.json()

    wallet_a = await client.get("/api/v1/economy", headers=ctx["headers_a"])
    assert wallet_a.json()["coins"] == finishing.json()["reward_coins"]  # not doubled


async def test_action_on_a_future_round_is_rejected(client, db_session, bot_token):
    ctx = await _make_two_heroes(client, db_session, bot_token, 20114, 20115)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    resp = await _submit(client, ctx["headers_a"], match["id"], 5)
    assert resp.status_code == 409


# --- skills / stun ---------------------------------------------------------------

async def test_stun_skill_discards_the_stunned_sides_action_that_round(client, db_session, bot_token):
    race = await create_race(db_session, code="race-stun-test")
    stun_class = await create_class(db_session, code="cls-stun-a", name="StunClass")
    stun_skill = await create_skill_definition(
        db_session, stun_class, code="stun1", name="Оглушение", skill_type=SkillType.stun,
        base_power=1, power_per_skill_level=0, cooldown_turns=10, required_hero_level=1,
    )
    template_a = await create_hero_template(db_session, name="Stunner", race=race, char_class=stun_class)
    template_b = await create_hero_template(db_session, name="Stunned", race=race)
    ctx = await _make_two_heroes(client, db_session, bot_token, 20116, 20117, template_a, template_b)

    upgrade = await client.post(f"/api/v1/heroes/me/skills/{stun_skill.id}/upgrade", headers=ctx["headers_a"])
    assert upgrade.status_code == 200

    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    match_id = match["id"]

    await _submit(client, ctx["headers_a"], match_id, 1, action_type="skill", skill_id=stun_skill.id)
    resp = await _submit(client, ctx["headers_b"], match_id, 1)
    body = resp.json()
    entry_types = [e["action_type"] for e in body["log"]]
    assert "stunned" in entry_types
    # b's HP is unaffected by a's stun cast (stun deals no direct damage)
    assert body["player_b"]["current_hp"] == 100


# --- timeout / sweep ---------------------------------------------------------------

async def test_timeout_sweep_defaults_the_afk_side_to_basic_attack(client, db_session, bot_token):
    ctx = await _make_two_heroes(client, db_session, bot_token, 20118, 20119)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    match_id = match["id"]

    await _submit(client, ctx["headers_a"], match_id, 1)  # b never responds
    await _force_overdue(db_session, match_id)

    resp = await client.get(f"/api/v1/arena/matches/{match_id}", headers=ctx["headers_a"])
    body = resp.json()
    assert body["current_round"] == 2  # resolved via the sweep, no action from b needed
    assert len(body["log"]) == 2
    assert body["player_a"]["current_hp"] == 99
    assert body["player_b"]["current_hp"] == 99


# --- snapshot invariance -----------------------------------------------------------

async def test_snapshot_is_frozen_at_match_creation_equipment_change_has_no_effect(client, db_session, bot_token):
    from tests.factories import create_item_template, grant_item_to_user
    from app.models.enums import EquipmentSlot, Rarity

    ctx = await _make_two_heroes(client, db_session, bot_token, 20120, 20121)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    match_id = match["id"]
    assert match["player_a"]["current_hp"] == 100  # base_hp, unequipped

    # Equip a strong item on hero_a AFTER the match already started.
    weapon = await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()
    user_a = await get_user_by_telegram_id(db_session, ctx["telegram_a"])
    item = await grant_item_to_user(db_session, user_a, weapon)
    await db_session.commit()
    equip_resp = await client.post(f"/api/v1/heroes/me/equipment/{item.id}/equip", headers=ctx["headers_a"])
    assert equip_resp.status_code == 200
    # Confirm equipping actually changed the hero's LIVE stats (so the test
    # would catch a leak if the match used them).
    hero_after_equip = await client.get("/api/v1/heroes/me", headers=ctx["headers_a"])
    assert hero_after_equip.json()["stats"]["attack"] > 10

    # Also bump hero level (changes hp/attack/defense/speed) and try to
    # learn a new skill after the match started.
    await set_hero_level(db_session, ctx["hero_a_id"], 10)
    await db_session.commit()

    await _submit(client, ctx["headers_a"], match_id, 1)
    resp = await _submit(client, ctx["headers_b"], match_id, 1)
    body = resp.json()
    # Still exactly the pre-match snapshot's damage: attack=10 (not the
    # equipped/leveled-up live value) vs defense=10 -> 1 damage, same as
    # test_first_action_waits_second_action_resolves_the_round with no
    # equipment/level change at all.
    assert body["player_b"]["current_hp"] == 99
    assert body["player_a"]["max_hp"] == 100  # not the level-10 HP value


# --- read endpoints ------------------------------------------------------------

async def test_get_match_detail_and_list(client, db_session, bot_token):
    ctx = await _make_two_heroes(client, db_session, bot_token, 20122, 20123)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])

    detail = await client.get(f"/api/v1/arena/matches/{match['id']}", headers=ctx["headers_a"])
    assert detail.status_code == 200
    assert detail.json()["id"] == match["id"]

    listing_a = await client.get("/api/v1/arena/matches", headers=ctx["headers_a"])
    assert any(m["id"] == match["id"] for m in listing_a.json())
    listing_b = await client.get("/api/v1/arena/matches", headers=ctx["headers_b"])
    assert any(m["id"] == match["id"] for m in listing_b.json())


async def test_get_match_detail_for_non_participant_is_404(client, db_session, bot_token):
    ctx = await _make_two_heroes(client, db_session, bot_token, 20124, 20125)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])

    headers_c = telegram_headers(20126, bot_token)
    await client.post("/api/v1/auth/session", headers=headers_c)
    resp = await client.get(f"/api/v1/arena/matches/{match['id']}", headers=headers_c)
    assert resp.status_code == 404


# --- concurrency: verified live against rpg-postgres, skipped here -----------

_CONCURRENCY_SKIP_REASON = (
    "Same documented SQLite limitation as every other Stage 3-8 "
    "concurrency test — no real row-level locking on a shared StaticPool "
    "connection. Kept as executable documentation; the real enforcement "
    "was verified live against rpg-postgres — see the Stage 9 report."
)


@pytest.mark.skip(reason=_CONCURRENCY_SKIP_REASON)
async def test_concurrent_actions_from_both_players_resolve_the_round_exactly_once(client, db_session, bot_token):
    from tests.conftest import TestSessionLocal

    ctx = await _make_two_heroes(client, db_session, bot_token, 20127, 20128)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    match_id = match["id"]

    async def attempt(telegram_id: int, label: str) -> str:
        async with TestSessionLocal() as session:
            from app.models.user import User as UserModel
            from app.services.arena_service import submit_action

            user = (
                await session.execute(select(UserModel).where(UserModel.telegram_id == telegram_id))
            ).scalar_one()
            try:
                out = await submit_action(session, user, match_id, 1, "basic_attack", None)
                return f"{label} ok round={out.current_round}"
            except Exception as exc:
                return f"{label} {type(exc).__name__}"

    from sqlalchemy import select

    results = await asyncio.gather(attempt(20127, "A"), attempt(20128, "B"))
    assert all("ok" in r for r in results)

    async with TestSessionLocal() as session:
        match_row = await session.get(ArenaMatch, match_id)
        assert match_row.current_round == 2
        assert len(match_row.log) == 2  # exactly one exchange, not two


@pytest.mark.skip(reason=_CONCURRENCY_SKIP_REASON)
async def test_concurrent_duplicate_retries_from_the_same_player_do_not_double_apply(client, db_session, bot_token):
    from tests.conftest import TestSessionLocal

    ctx = await _make_two_heroes(client, db_session, bot_token, 20129, 20130)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    match_id = match["id"]

    async def attempt() -> str:
        async with TestSessionLocal() as session:
            from sqlalchemy import select

            from app.models.user import User as UserModel
            from app.services.arena_service import submit_action

            user = (
                await session.execute(select(UserModel).where(UserModel.telegram_id == 20129))
            ).scalar_one()
            try:
                await submit_action(session, user, match_id, 1, "basic_attack", None)
                return "ok"
            except Exception as exc:
                return type(exc).__name__

    results = await asyncio.gather(attempt(), attempt())
    assert results == ["ok", "ok"]  # both succeed (idempotent replay), no error

    async with TestSessionLocal() as session:
        match_row = await session.get(ArenaMatch, match_id)
        assert match_row.state["player_a"]["pending_action"] is not None
        assert match_row.current_round == 1  # still waiting on b, not advanced twice


@pytest.mark.skip(reason=_CONCURRENCY_SKIP_REASON)
async def test_concurrent_finishing_round_grants_reward_exactly_once(client, db_session, bot_token):
    from tests.conftest import TestSessionLocal

    ctx = await _make_lopsided_heroes(client, db_session, bot_token, 20131, 20132)
    match = await _create_match(client, ctx["headers_a"], ctx["user_b_id"])
    match_id = match["id"]
    await _submit(client, ctx["headers_a"], match_id, 1)

    async def attempt(telegram_id: int) -> str:
        async with TestSessionLocal() as session:
            from sqlalchemy import select

            from app.models.user import User as UserModel
            from app.services.arena_service import submit_action

            user = (
                await session.execute(select(UserModel).where(UserModel.telegram_id == telegram_id))
            ).scalar_one()
            try:
                await submit_action(session, user, match_id, 1, "basic_attack", None)
                return "ok"
            except Exception as exc:
                return type(exc).__name__

    # b submits twice "concurrently" — the finishing action and a retry of it.
    results = await asyncio.gather(attempt(20132, ), attempt(20132))
    assert results == ["ok", "ok"]

    async with TestSessionLocal() as session:
        from tests.factories import get_user_by_telegram_id as _get

        winner = await _get(session, 20131)
        assert winner.balance == 30  # ARENA_WIN_REWARD_COINS, credited exactly once
