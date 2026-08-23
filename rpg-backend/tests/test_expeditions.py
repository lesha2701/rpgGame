import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from tests.factories import create_expedition_template, create_hero_template, set_hero_level
from tests.utils import telegram_headers

from app.models.user_expedition import UserExpedition
from app.services.expedition_service import _is_time_complete
from app.services.progression import xp_to_next_level


async def _make_hero(client, db_session, telegram_id, bot_token, level: int = 1):
    template = await create_hero_template(db_session, name=f"Герой{telegram_id}")
    await db_session.commit()
    headers = telegram_headers(telegram_id, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id, "name": "Герой"})
    assert resp.status_code == 201
    hero_id = resp.json()["id"]
    if level != 1:
        await set_hero_level(db_session, hero_id, level)
        await db_session.commit()
    return hero_id, headers


async def _force_completed(db_session, user_expedition_id: int, seconds_ago: int = 1) -> None:
    """Simulates "time has passed" (including "the server was off the whole
    time") without actually waiting — moves completed_at into the past.
    Nothing about claim()'s check depends on a process having been running
    while that time elapsed, which is the whole point of Stage 7."""
    row = await db_session.get(UserExpedition, user_expedition_id)
    row.completed_at = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    db_session.add(row)
    await db_session.commit()


# --- pure timestamp logic (no DB) --------------------------------------------

def test_is_time_complete_exactly_at_the_boundary_counts_as_complete():
    class _Row:
        completed_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert _is_time_complete(_Row(), now) is True  # >=, not >


def test_is_time_complete_one_second_before_is_not_complete():
    class _Row:
        completed_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    now = datetime(2026, 1, 1, 11, 59, 59, tzinfo=timezone.utc)
    assert _is_time_complete(_Row(), now) is False


# --- catalog -------------------------------------------------------------------

async def test_catalog_reports_availability_per_hero_level(client, db_session, bot_token):
    low = await create_expedition_template(db_session, name="Low", required_hero_level=1)
    high = await create_expedition_template(db_session, name="High", required_hero_level=10)
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10001, bot_token, level=1)

    resp = await client.get("/api/v1/expeditions", headers=headers)
    assert resp.status_code == 200
    by_id = {e["id"]: e for e in resp.json()}
    assert by_id[low.id]["is_available_to_user"] is True
    assert by_id[high.id]["is_available_to_user"] is False
    assert by_id[high.id]["required_hero_level"] == 10


async def test_inactive_expeditions_are_excluded_from_the_catalog(client, db_session, bot_token):
    await create_expedition_template(db_session, name="Hidden", is_active=False)
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10002, bot_token, level=1)

    resp = await client.get("/api/v1/expeditions", headers=headers)
    assert resp.json() == []


async def test_expedition_detail_404_for_unknown_id(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 10003, bot_token, level=1)
    resp = await client.get("/api/v1/expeditions/999999", headers=headers)
    assert resp.status_code == 404


# --- start -----------------------------------------------------------------

async def test_start_creates_a_running_expedition(client, db_session, bot_token):
    expedition = await create_expedition_template(db_session, name="E1", duration_seconds=600)
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10004, bot_token, level=1)

    resp = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "running"
    assert body["claimed_at"] is None
    assert body["expedition"]["id"] == expedition.id


async def test_cannot_start_below_required_hero_level(client, db_session, bot_token):
    expedition = await create_expedition_template(db_session, name="E1", required_hero_level=10)
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10005, bot_token, level=1)

    resp = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
    assert resp.status_code == 409


async def test_cannot_start_an_inactive_expedition(client, db_session, bot_token):
    expedition = await create_expedition_template(db_session, name="E1", is_active=False)
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10006, bot_token, level=1)

    resp = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
    assert resp.status_code == 409


async def test_cannot_start_a_second_expedition_while_one_is_running(client, db_session, bot_token):
    e1 = await create_expedition_template(db_session, name="E1")
    e2 = await create_expedition_template(db_session, name="E2")
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10007, bot_token, level=1)

    first = await client.post(f"/api/v1/expeditions/{e1.id}/start", headers=headers)
    assert first.status_code == 201
    second = await client.post(f"/api/v1/expeditions/{e2.id}/start", headers=headers)
    assert second.status_code == 409


async def test_unknown_expedition_start_is_404(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 10008, bot_token, level=1)
    resp = await client.post("/api/v1/expeditions/999999/start", headers=headers)
    assert resp.status_code == 404


async def test_starting_without_a_hero_is_404(client, db_session, bot_token):
    expedition = await create_expedition_template(db_session, name="E1")
    await db_session.commit()
    headers = telegram_headers(10009, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
    assert resp.status_code == 404


# --- current expedition -----------------------------------------------------

async def test_current_expedition_is_null_when_none_running(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 10010, bot_token, level=1)
    resp = await client.get("/api/v1/heroes/me/expedition", headers=headers)
    assert resp.status_code == 200
    assert resp.json() is None


async def test_current_expedition_reflects_the_running_one(client, db_session, bot_token):
    expedition = await create_expedition_template(db_session, name="E1")
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10011, bot_token, level=1)
    started = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)

    resp = await client.get("/api/v1/heroes/me/expedition", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == started.json()["id"]


# --- claim: duration gating ---------------------------------------------------

async def test_claim_before_completion_is_rejected(client, db_session, bot_token):
    expedition = await create_expedition_template(db_session, name="E1", duration_seconds=3600)
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10012, bot_token, level=1)
    started = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
    user_expedition_id = started.json()["id"]

    resp = await client.post(f"/api/v1/expeditions/{user_expedition_id}/claim", headers=headers)
    assert resp.status_code == 409
    assert "completes_at" in resp.json()["error"]["details"]


async def test_claim_after_completion_succeeds_even_if_the_server_was_down_the_whole_time(
    client, db_session, bot_token
):
    expedition = await create_expedition_template(db_session, name="E1", duration_seconds=36000)
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10013, bot_token, level=1)
    started = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
    user_expedition_id = started.json()["id"]

    # Simulate the server being off for the entire 10-hour duration: nudge
    # completed_at into the past directly, no sleeping, no background job
    # involved anywhere in this flow.
    await _force_completed(db_session, user_expedition_id, seconds_ago=1)

    resp = await client.post(f"/api/v1/expeditions/{user_expedition_id}/claim", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "claimed"


# --- claim: rewards ------------------------------------------------------------

async def test_claim_grants_xp_and_coins(client, db_session, bot_token):
    expedition = await create_expedition_template(
        db_session, name="E1", duration_seconds=1, reward_xp=25, reward_coins=10
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10014, bot_token, level=1)
    started = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
    user_expedition_id = started.json()["id"]
    await _force_completed(db_session, user_expedition_id)

    resp = await client.post(f"/api/v1/expeditions/{user_expedition_id}/claim", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["reward_xp"] == 25
    assert body["reward_coins"] == 10
    assert body["hero_xp"] == 25
    assert body["balance"] == 10

    wallet = await client.get("/api/v1/economy", headers=headers)
    assert wallet.json()["coins"] == 10


async def test_claim_can_level_up_the_hero(client, db_session, bot_token):
    expedition = await create_expedition_template(
        db_session, name="E1", duration_seconds=1, reward_xp=xp_to_next_level(1), reward_coins=0
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10015, bot_token, level=1)
    started = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
    user_expedition_id = started.json()["id"]
    await _force_completed(db_session, user_expedition_id)

    resp = await client.post(f"/api/v1/expeditions/{user_expedition_id}/claim", headers=headers)
    body = resp.json()
    assert body["hero_level"] == 2
    assert body["hero_xp"] == 0


async def test_claiming_again_grants_nothing_more(client, db_session, bot_token):
    expedition = await create_expedition_template(
        db_session, name="E1", duration_seconds=1, reward_xp=25, reward_coins=10
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10016, bot_token, level=1)
    started = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
    user_expedition_id = started.json()["id"]
    await _force_completed(db_session, user_expedition_id)

    first = await client.post(f"/api/v1/expeditions/{user_expedition_id}/claim", headers=headers)
    second = await client.post(f"/api/v1/expeditions/{user_expedition_id}/claim", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "claimed"

    wallet = await client.get("/api/v1/economy", headers=headers)
    assert wallet.json()["coins"] == 10  # granted exactly once, not twice

    heroes_me = await client.get("/api/v1/heroes/me", headers=headers)
    assert heroes_me.json()["xp"] == 25  # granted exactly once, not twice


async def test_after_claim_hero_can_start_a_new_expedition(client, db_session, bot_token):
    expedition = await create_expedition_template(db_session, name="E1", duration_seconds=1)
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10017, bot_token, level=1)
    started = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
    user_expedition_id = started.json()["id"]
    await _force_completed(db_session, user_expedition_id)
    await client.post(f"/api/v1/expeditions/{user_expedition_id}/claim", headers=headers)

    resp = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
    assert resp.status_code == 201


# --- ownership / not found ------------------------------------------------------

async def test_claiming_someone_elses_expedition_is_404(client, db_session, bot_token):
    expedition = await create_expedition_template(db_session, name="E1", duration_seconds=1)
    # One shared HeroTemplate for both users — _make_hero's default path
    # creates its own Race/CharacterClass (code="human"/"warrior") per call,
    # which collides on a second call in the same test (unique code column);
    # a HeroTemplate has no such per-user uniqueness constraint, so reusing
    # one across two different users' heroes is fine.
    hero_template = await create_hero_template(db_session, name="Shared")
    await db_session.commit()

    headers_a = telegram_headers(10018, bot_token)
    await client.post("/api/v1/auth/session", headers=headers_a)
    await client.post("/api/v1/heroes", headers=headers_a, json={"hero_template_id": hero_template.id, "name": "Герой"})
    started = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers_a)
    user_expedition_id = started.json()["id"]

    headers_b = telegram_headers(10019, bot_token)
    await client.post("/api/v1/auth/session", headers=headers_b)
    await client.post("/api/v1/heroes", headers=headers_b, json={"hero_template_id": hero_template.id, "name": "Герой"})
    resp = await client.post(f"/api/v1/expeditions/{user_expedition_id}/claim", headers=headers_b)
    assert resp.status_code == 404


async def test_unknown_user_expedition_claim_is_404(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 10020, bot_token, level=1)
    resp = await client.post("/api/v1/expeditions/999999/claim", headers=headers)
    assert resp.status_code == 404


# --- history -------------------------------------------------------------------

async def test_expedition_history_lists_past_expeditions_newest_first(client, db_session, bot_token):
    e1 = await create_expedition_template(db_session, name="E1", duration_seconds=1)
    e2 = await create_expedition_template(db_session, name="E2", duration_seconds=1)
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10021, bot_token, level=1)

    first = await client.post(f"/api/v1/expeditions/{e1.id}/start", headers=headers)
    await _force_completed(db_session, first.json()["id"])
    await client.post(f"/api/v1/expeditions/{first.json()['id']}/claim", headers=headers)

    second = await client.post(f"/api/v1/expeditions/{e2.id}/start", headers=headers)

    history = await client.get("/api/v1/expeditions/history", headers=headers)
    assert history.status_code == 200
    ids = [h["id"] for h in history.json()]
    assert ids == [second.json()["id"], first.json()["id"]]
    statuses = {h["id"]: h["status"] for h in history.json()}
    assert statuses[first.json()["id"]] == "claimed"
    assert statuses[second.json()["id"]] == "running"


# --- timezone correctness (SQLite returns naive datetimes for these columns) --

async def test_claim_works_with_naive_timestamps_from_sqlite(client, db_session, bot_token):
    """Regression guard for the ensure_aware() wrapping in expedition_service:
    without it, comparing a naive datetime (what SQLite hands back for a
    DateTime(timezone=True) column) against datetime.now(timezone.utc) would
    raise TypeError instead of ever returning a clean 409/200."""
    expedition = await create_expedition_template(db_session, name="E1", duration_seconds=36000)
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10022, bot_token, level=1)
    started = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
    user_expedition_id = started.json()["id"]

    too_early = await client.post(f"/api/v1/expeditions/{user_expedition_id}/claim", headers=headers)
    assert too_early.status_code == 409

    await _force_completed(db_session, user_expedition_id)
    ready = await client.post(f"/api/v1/expeditions/{user_expedition_id}/claim", headers=headers)
    assert ready.status_code == 200


# --- concurrency: verified live against rpg-postgres, skipped here -----------

@pytest.mark.skip(
    reason=(
        "Same documented SQLite limitation as every other Stage 3-6 "
        "concurrency test — no real row-level locking on a shared "
        "StaticPool connection. Kept as executable documentation; the real "
        "enforcement was verified live against rpg-postgres — see the "
        "Stage 7 report."
    )
)
async def test_concurrent_claims_grant_the_reward_exactly_once(client, db_session, bot_token):
    from tests.conftest import TestSessionLocal
    from tests.factories import get_user_by_telegram_id

    expedition = await create_expedition_template(
        db_session, name="E1", duration_seconds=1, reward_xp=25, reward_coins=10
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10023, bot_token, level=1)
    started = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
    user_expedition_id = started.json()["id"]
    await _force_completed(db_session, user_expedition_id)

    user = await get_user_by_telegram_id(db_session, 10023)
    user_id = user.id

    async def attempt() -> str:
        async with TestSessionLocal() as session:
            from app.models.user import User as UserModel
            from app.services.expedition_service import claim_expedition
            from app.services.hero_service import get_active_hero

            u = await session.get(UserModel, user_id)
            hero = await get_active_hero(session, u)
            try:
                await claim_expedition(session, u, hero, user_expedition_id)
                return "ok"
            except Exception as exc:
                return type(exc).__name__

    results = await asyncio.gather(attempt(), attempt())
    assert results == ["ok", "ok"]

    async with TestSessionLocal() as session:
        refreshed = await get_user_by_telegram_id(session, 10023)
        assert refreshed.balance == 10  # credited exactly once


@pytest.mark.skip(
    reason=(
        "Same documented SQLite limitation as every other Stage 3-6 "
        "concurrency test. Kept as executable documentation; the real "
        "enforcement (one hero can't end up in two running expeditions) "
        "was verified live against rpg-postgres — see the Stage 7 report."
    )
)
async def test_concurrent_starts_never_leave_a_hero_in_two_running_expeditions(client, db_session, bot_token):
    from tests.conftest import TestSessionLocal
    from tests.factories import get_user_by_telegram_id

    e1 = await create_expedition_template(db_session, name="E1")
    e2 = await create_expedition_template(db_session, name="E2")
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 10024, bot_token, level=1)

    user = await get_user_by_telegram_id(db_session, 10024)
    user_id = user.id

    async def attempt(template_id: int) -> str:
        async with TestSessionLocal() as session:
            from app.models.user import User as UserModel
            from app.services.expedition_service import start_expedition
            from app.services.hero_service import get_active_hero

            u = await session.get(UserModel, user_id)
            hero = await get_active_hero(session, u)
            try:
                await start_expedition(session, u, hero, template_id)
                return "ok"
            except Exception as exc:
                return type(exc).__name__

    results = await asyncio.gather(attempt(e1.id), attempt(e2.id))
    assert sorted(results) == ["ConflictError", "ok"]

    async with TestSessionLocal() as session:
        from sqlalchemy import select

        from app.models.enums import ExpeditionStatus

        running = (
            await session.execute(
                select(UserExpedition).where(
                    UserExpedition.user_id == user_id, UserExpedition.status == ExpeditionStatus.running
                )
            )
        ).scalars().all()
        assert len(running) == 1
