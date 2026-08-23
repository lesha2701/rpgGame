import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from tests.factories import (
    create_chest,
    create_class,
    create_enemy_template,
    create_expedition_template,
    create_hero_template,
    create_item_template,
    create_quest_definition,
    create_skill_definition,
    get_user_by_telegram_id,
    set_hero_level,
)
from tests.utils import telegram_headers

from app.models.enums import EquipmentSlot, QuestConditionType, Rarity, TransactionType
from app.models.user_expedition import UserExpedition
from app.services.progression import xp_to_next_level
from app.services.wallet_service import credit_coins


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


async def _fund(db_session, telegram_id, amount):
    user = await get_user_by_telegram_id(db_session, telegram_id)
    await credit_coins(db_session, user, amount, TransactionType.admin_grant)
    await db_session.commit()


async def _win_battles(client, db_session, headers, count: int) -> None:
    enemy = await create_enemy_template(db_session, name=f"Мишень{count}-{id(object())}", hp=1, attack=1, defense=0, speed=1)
    await db_session.commit()
    for _ in range(count):
        resp = await client.post("/api/v1/battles", headers=headers, json={"enemy_template_id": enemy.id})
        assert resp.status_code == 201
        assert resp.json()["result"] == "won"


async def _claim_expeditions(client, db_session, headers, count: int) -> None:
    expedition = await create_expedition_template(
        db_session, name=f"Эксп{count}-{id(object())}", duration_seconds=1, reward_xp=1, reward_coins=1
    )
    await db_session.commit()
    for _ in range(count):
        started = await client.post(f"/api/v1/expeditions/{expedition.id}/start", headers=headers)
        assert started.status_code == 201
        user_expedition_id = started.json()["id"]
        row = await db_session.get(UserExpedition, user_expedition_id)
        row.completed_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db_session.add(row)
        await db_session.commit()
        claimed = await client.post(f"/api/v1/expeditions/{user_expedition_id}/claim", headers=headers)
        assert claimed.status_code == 200


async def _open_chests(client, db_session, telegram_id, headers, count: int) -> None:
    chest = await create_chest(db_session, price=1, slug=f"quest-test-chest-{id(object())}")
    await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    await db_session.commit()
    await _fund(db_session, telegram_id, 10_000)
    for _ in range(count):
        resp = await client.post(f"/api/v1/chests/{chest.id}/open", headers=headers, json={})
        assert resp.status_code == 200


def _quest_by_code(quests: list[dict], code: str) -> dict:
    return next(q for q in quests if q["code"] == code)


# --- catalog / listing ----------------------------------------------------

async def test_list_quests_shows_zero_progress_for_a_fresh_hero(client, db_session, bot_token):
    await create_quest_definition(
        db_session, code="q1", name="Q1", condition_type=QuestConditionType.battles_won, target_value=1
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11001, bot_token, level=1)

    resp = await client.get("/api/v1/quests", headers=headers)
    assert resp.status_code == 200
    q1 = _quest_by_code(resp.json(), "q1")
    assert q1["current_progress"] == 0
    assert q1["is_completed"] is False
    assert q1["is_claimed"] is False


async def test_inactive_quests_are_excluded(client, db_session, bot_token):
    await create_quest_definition(db_session, code="hidden", name="Hidden", is_active=False)
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11002, bot_token, level=1)

    resp = await client.get("/api/v1/quests", headers=headers)
    codes = [q["code"] for q in resp.json()]
    assert "hidden" not in codes


async def test_quests_visible_without_an_active_hero(client, bot_token):
    headers = telegram_headers(11003, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.get("/api/v1/quests", headers=headers)
    assert resp.status_code == 200  # not a 404 — see quests router's comment


async def test_claiming_without_a_hero_is_404(client, db_session, bot_token):
    quest = await create_quest_definition(db_session, code="q1", target_value=1)
    await db_session.commit()
    headers = telegram_headers(11004, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post(f"/api/v1/quests/{quest.id}/claim", headers=headers)
    assert resp.status_code == 404


# --- condition types: progress reflects real gameplay, nothing is cached -----

async def test_battles_won_progress(client, db_session, bot_token):
    await create_quest_definition(
        db_session, code="bw", condition_type=QuestConditionType.battles_won, target_value=2
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11005, bot_token, level=1)

    resp = await client.get("/api/v1/quests", headers=headers)
    assert _quest_by_code(resp.json(), "bw")["current_progress"] == 0

    await _win_battles(client, db_session, headers, 1)
    resp = await client.get("/api/v1/quests", headers=headers)
    bw = _quest_by_code(resp.json(), "bw")
    assert bw["current_progress"] == 1
    assert bw["is_completed"] is False

    await _win_battles(client, db_session, headers, 1)
    resp = await client.get("/api/v1/quests", headers=headers)
    bw = _quest_by_code(resp.json(), "bw")
    assert bw["current_progress"] == 2
    assert bw["is_completed"] is True


async def test_expeditions_claimed_progress(client, db_session, bot_token):
    await create_quest_definition(
        db_session, code="ec", condition_type=QuestConditionType.expeditions_claimed, target_value=1
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11006, bot_token, level=1)

    await _claim_expeditions(client, db_session, headers, 1)
    resp = await client.get("/api/v1/quests", headers=headers)
    assert _quest_by_code(resp.json(), "ec")["current_progress"] == 1


async def test_chests_opened_progress(client, db_session, bot_token):
    await create_quest_definition(
        db_session, code="co", condition_type=QuestConditionType.chests_opened, target_value=2
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11007, bot_token, level=1)

    await _open_chests(client, db_session, 11007, headers, 2)
    resp = await client.get("/api/v1/quests", headers=headers)
    assert _quest_by_code(resp.json(), "co")["current_progress"] == 2


async def test_hero_level_progress(client, db_session, bot_token):
    await create_quest_definition(
        db_session, code="hl", condition_type=QuestConditionType.hero_level, target_value=5
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11008, bot_token, level=3)

    resp = await client.get("/api/v1/quests", headers=headers)
    hl = _quest_by_code(resp.json(), "hl")
    assert hl["current_progress"] == 3
    assert hl["is_completed"] is False

    await set_hero_level(db_session, _hero_id, 5)
    await db_session.commit()
    resp = await client.get("/api/v1/quests", headers=headers)
    hl = _quest_by_code(resp.json(), "hl")
    assert hl["current_progress"] == 5
    assert hl["is_completed"] is True


async def test_items_equipped_progress_reflects_currently_equipped_count(client, db_session, bot_token):
    await create_quest_definition(
        db_session, code="ie", condition_type=QuestConditionType.items_equipped, target_value=2
    )
    weapon = await create_item_template(db_session, slot=EquipmentSlot.weapon, tier=1, rarity=Rarity.common)
    helmet = await create_item_template(db_session, slot=EquipmentSlot.helmet, tier=1, rarity=Rarity.common)
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11009, bot_token, level=1)

    from tests.factories import grant_item_to_user

    user = await get_user_by_telegram_id(db_session, 11009)
    item1 = await grant_item_to_user(db_session, user, weapon)
    item2 = await grant_item_to_user(db_session, user, helmet)
    await db_session.commit()

    resp = await client.get("/api/v1/quests", headers=headers)
    assert _quest_by_code(resp.json(), "ie")["current_progress"] == 0

    await client.post(f"/api/v1/heroes/me/equipment/{item1.id}/equip", headers=headers)
    resp = await client.get("/api/v1/quests", headers=headers)
    assert _quest_by_code(resp.json(), "ie")["current_progress"] == 1

    await client.post(f"/api/v1/heroes/me/equipment/{item2.id}/equip", headers=headers)
    resp = await client.get("/api/v1/quests", headers=headers)
    ie = _quest_by_code(resp.json(), "ie")
    assert ie["current_progress"] == 2
    assert ie["is_completed"] is True


async def test_skills_upgraded_progress_is_cumulative_upgrade_actions(client, db_session, bot_token):
    await create_quest_definition(
        db_session, code="su", condition_type=QuestConditionType.skills_upgraded, target_value=3
    )
    char_class = await create_class(db_session, code="cls-quest", name="ТестКласс")
    skill = await create_skill_definition(db_session, char_class, code="s1", name="Навык", required_hero_level=1)
    template = await create_hero_template(db_session, name="Герой-навыки", char_class=char_class)
    await db_session.commit()
    headers = telegram_headers(11010, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    create_resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id})
    hero_id = create_resp.json()["id"]
    await set_hero_level(db_session, hero_id, 5)  # budget=5, enough for 3 upgrades of the same skill
    await db_session.commit()

    await client.post(f"/api/v1/heroes/me/skills/{skill.id}/upgrade", headers=headers)
    await client.post(f"/api/v1/heroes/me/skills/{skill.id}/upgrade", headers=headers)
    resp = await client.get("/api/v1/quests", headers=headers)
    assert _quest_by_code(resp.json(), "su")["current_progress"] == 2

    await client.post(f"/api/v1/heroes/me/skills/{skill.id}/upgrade", headers=headers)
    resp = await client.get("/api/v1/quests", headers=headers)
    su = _quest_by_code(resp.json(), "su")
    assert su["current_progress"] == 3
    assert su["is_completed"] is True


# --- claim ---------------------------------------------------------------

async def test_claiming_a_completed_quest_grants_xp_and_coins(client, db_session, bot_token):
    quest = await create_quest_definition(
        db_session, code="cq", condition_type=QuestConditionType.battles_won, target_value=1,
        reward_xp=25, reward_coins=15,
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11011, bot_token, level=1)
    await _win_battles(client, db_session, headers, 1)

    listed = await client.get("/api/v1/quests", headers=headers)
    user_quest_id = _quest_by_code(listed.json(), "cq")["id"]

    resp = await client.post(f"/api/v1/quests/{user_quest_id}/claim", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["reward_xp"] == 25
    assert body["reward_coins"] == 15
    assert body["hero_progress"]["xp"] >= 25
    assert body["hero_progress"]["balance"] >= 15

    wallet = await client.get("/api/v1/economy", headers=headers)
    assert wallet.json()["coins"] == body["hero_progress"]["balance"]


async def test_claim_creates_a_coin_transaction(client, db_session, bot_token):
    quest = await create_quest_definition(
        db_session, code="tx", condition_type=QuestConditionType.battles_won, target_value=1,
        reward_xp=10, reward_coins=20,
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11012, bot_token, level=1)
    await _win_battles(client, db_session, headers, 1)
    listed = await client.get("/api/v1/quests", headers=headers)
    user_quest_id = _quest_by_code(listed.json(), "tx")["id"]

    await client.post(f"/api/v1/quests/{user_quest_id}/claim", headers=headers)

    from sqlalchemy import select

    from app.models.transaction import CoinTransaction

    user = await get_user_by_telegram_id(db_session, 11012)
    txs = (
        await db_session.execute(
            select(CoinTransaction).where(
                CoinTransaction.user_id == user.id, CoinTransaction.type == TransactionType.quest_reward
            )
        )
    ).scalars().all()
    assert len(txs) == 1
    assert txs[0].amount == 20
    assert txs[0].related_object_type == "user_quest"
    assert txs[0].related_object_id == user_quest_id


async def test_claiming_an_incomplete_quest_is_409(client, db_session, bot_token):
    quest = await create_quest_definition(
        db_session, code="inc", condition_type=QuestConditionType.battles_won, target_value=5
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11013, bot_token, level=1)
    await _win_battles(client, db_session, headers, 1)
    listed = await client.get("/api/v1/quests", headers=headers)
    user_quest_id = _quest_by_code(listed.json(), "inc")["id"]

    resp = await client.post(f"/api/v1/quests/{user_quest_id}/claim", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["details"]["current_progress"] == 1
    assert resp.json()["error"]["details"]["target_value"] == 5


async def test_claiming_an_already_claimed_quest_is_409(client, db_session, bot_token):
    quest = await create_quest_definition(
        db_session, code="dup", condition_type=QuestConditionType.battles_won, target_value=1
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11014, bot_token, level=1)
    await _win_battles(client, db_session, headers, 1)
    listed = await client.get("/api/v1/quests", headers=headers)
    user_quest_id = _quest_by_code(listed.json(), "dup")["id"]

    first = await client.post(f"/api/v1/quests/{user_quest_id}/claim", headers=headers)
    assert first.status_code == 200
    second = await client.post(f"/api/v1/quests/{user_quest_id}/claim", headers=headers)
    assert second.status_code == 409

    wallet = await client.get("/api/v1/economy", headers=headers)
    assert wallet.json()["coins"] == first.json()["hero_progress"]["balance"]  # not granted twice


async def test_claiming_someone_elses_quest_is_404(client, db_session, bot_token):
    await create_quest_definition(db_session, code="q1", condition_type=QuestConditionType.battles_won, target_value=1)
    hero_template = await create_hero_template(db_session, name="Shared")
    await db_session.commit()

    headers_a = telegram_headers(11015, bot_token)
    await client.post("/api/v1/auth/session", headers=headers_a)
    await client.post("/api/v1/heroes", headers=headers_a, json={"hero_template_id": hero_template.id})
    listed = await client.get("/api/v1/quests", headers=headers_a)
    user_quest_id = _quest_by_code(listed.json(), "q1")["id"]

    headers_b = telegram_headers(11016, bot_token)
    await client.post("/api/v1/auth/session", headers=headers_b)
    await client.post("/api/v1/heroes", headers=headers_b, json={"hero_template_id": hero_template.id})
    resp = await client.post(f"/api/v1/quests/{user_quest_id}/claim", headers=headers_b)
    assert resp.status_code == 404


async def test_unknown_quest_claim_is_404(client, db_session, bot_token):
    _hero_id, headers = await _make_hero(client, db_session, 11017, bot_token, level=1)
    resp = await client.post("/api/v1/quests/999999/claim", headers=headers)
    assert resp.status_code == 404


async def test_claim_can_level_up_the_hero(client, db_session, bot_token):
    quest = await create_quest_definition(
        db_session, code="lvl", condition_type=QuestConditionType.battles_won, target_value=1,
        reward_xp=xp_to_next_level(1), reward_coins=0,
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11018, bot_token, level=1)
    await _win_battles(client, db_session, headers, 1)
    listed = await client.get("/api/v1/quests", headers=headers)
    user_quest_id = _quest_by_code(listed.json(), "lvl")["id"]

    resp = await client.post(f"/api/v1/quests/{user_quest_id}/claim", headers=headers)
    body = resp.json()
    # xp_to_next_level(1) was already partly consumed by the battle-win XP
    # the quest itself required — assert we crossed to at least level 2,
    # not an exact level, since _win_battles' battle also grants XP.
    assert body["hero_progress"]["level"] >= 2


async def test_multiple_quests_progress_independently(client, db_session, bot_token):
    await create_quest_definition(db_session, code="m1", condition_type=QuestConditionType.battles_won, target_value=1)
    await create_quest_definition(db_session, code="m2", condition_type=QuestConditionType.chests_opened, target_value=1)
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11019, bot_token, level=1)

    await _win_battles(client, db_session, headers, 1)
    resp = await client.get("/api/v1/quests", headers=headers)
    quests = resp.json()
    m1 = _quest_by_code(quests, "m1")
    m2 = _quest_by_code(quests, "m2")
    assert m1["is_completed"] is True
    assert m2["is_completed"] is False  # unaffected by the battle win


async def test_progress_is_never_stored_reads_are_always_live(client, db_session, bot_token):
    """No column anywhere records progress — every GET recomputes it from
    Battle/etc. directly. Proven by playing between two GETs with no
    explicit "sync" step in between; if progress were cached/stored, the
    second GET wouldn't reflect the win without something updating it."""
    await create_quest_definition(db_session, code="live", condition_type=QuestConditionType.battles_won, target_value=10)
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11020, bot_token, level=1)

    before = await client.get("/api/v1/quests", headers=headers)
    assert _quest_by_code(before.json(), "live")["current_progress"] == 0

    await _win_battles(client, db_session, headers, 3)

    after = await client.get("/api/v1/quests", headers=headers)
    assert _quest_by_code(after.json(), "live")["current_progress"] == 3


# --- slot rotation ---------------------------------------------------------

async def test_only_5_quests_are_active_at_once_from_a_larger_pool(client, db_session, bot_token):
    for i in range(8):
        await create_quest_definition(
            db_session, code=f"pool{i}", condition_type=QuestConditionType.battles_won, target_value=1
        )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11022, bot_token, level=1)

    resp = await client.get("/api/v1/quests", headers=headers)
    quests = resp.json()
    active = [q for q in quests if q["is_active_slot"]]
    assert len(active) == 5
    assert len(quests) == 5  # unclaimed non-slotted rows don't exist — only the drawn 5 appear


async def test_claiming_frees_the_slot_and_draws_a_replacement(client, db_session, bot_token):
    for i in range(6):
        await create_quest_definition(
            db_session, code=f"rot{i}", condition_type=QuestConditionType.battles_won, target_value=1,
            reward_xp=5, reward_coins=5,
        )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11023, bot_token, level=1)
    await _win_battles(client, db_session, headers, 1)  # satisfies every battles_won/1 quest at once

    listed = await client.get("/api/v1/quests", headers=headers)
    before_codes = {q["code"] for q in listed.json() if q["is_active_slot"]}
    assert len(before_codes) == 5

    claim_target = next(q for q in listed.json() if q["is_active_slot"])
    resp = await client.post(f"/api/v1/quests/{claim_target['id']}/claim", headers=headers)
    assert resp.status_code == 200

    after = await client.get("/api/v1/quests", headers=headers)
    after_active = [q for q in after.json() if q["is_active_slot"]]
    assert len(after_active) == 5  # slot was refilled, not left empty
    after_codes = {q["code"] for q in after_active}
    assert claim_target["code"] not in after_codes  # the claimed one moved out of the active set
    assert after_codes != before_codes  # the 6th pool definition took its place


async def test_claimed_quest_stays_visible_as_history_not_deleted(client, db_session, bot_token):
    await create_quest_definition(
        db_session, code="hist", condition_type=QuestConditionType.battles_won, target_value=1
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11024, bot_token, level=1)
    await _win_battles(client, db_session, headers, 1)

    listed = await client.get("/api/v1/quests", headers=headers)
    user_quest_id = _quest_by_code(listed.json(), "hist")["id"]
    await client.post(f"/api/v1/quests/{user_quest_id}/claim", headers=headers)

    after = await client.get("/api/v1/quests", headers=headers)
    hist = _quest_by_code(after.json(), "hist")
    assert hist["is_claimed"] is True
    assert hist["is_active_slot"] is False  # freed its slot, but the row itself is still returned


async def test_a_definition_is_never_reassigned_to_the_same_user_twice(client, db_session, bot_token):
    # Only 1 definition exists — after it's claimed, the pool is empty, so
    # the freed slot must NOT be refilled by drawing the same definition
    # again (non-repeatable pool — see UserQuest's docstring).
    await create_quest_definition(
        db_session, code="once", condition_type=QuestConditionType.battles_won, target_value=1
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11025, bot_token, level=1)
    await _win_battles(client, db_session, headers, 1)

    listed = await client.get("/api/v1/quests", headers=headers)
    user_quest_id = _quest_by_code(listed.json(), "once")["id"]
    await client.post(f"/api/v1/quests/{user_quest_id}/claim", headers=headers)

    after = await client.get("/api/v1/quests", headers=headers)
    codes = [q["code"] for q in after.json()]
    assert codes.count("once") == 1  # still present exactly once, as history — not redrawn into a slot
    once = _quest_by_code(after.json(), "once")
    assert once["is_active_slot"] is False


# --- concurrency: verified live against rpg-postgres, skipped here -----------

@pytest.mark.skip(
    reason=(
        "Same documented SQLite limitation as every other Stage 3-7 "
        "concurrency test — no real row-level locking on a shared "
        "StaticPool connection. Kept as executable documentation; the real "
        "enforcement was verified live against rpg-postgres — see the "
        "Stage 8 report."
    )
)
async def test_concurrent_claims_grant_the_reward_exactly_once(client, db_session, bot_token):
    from tests.conftest import TestSessionLocal

    await create_quest_definition(
        db_session, code="race", condition_type=QuestConditionType.battles_won, target_value=1,
        reward_xp=10, reward_coins=10,
    )
    await db_session.commit()
    _hero_id, headers = await _make_hero(client, db_session, 11021, bot_token, level=1)
    await _win_battles(client, db_session, headers, 1)
    listed = await client.get("/api/v1/quests", headers=headers)
    user_quest_id = _quest_by_code(listed.json(), "race")["id"]

    user = await get_user_by_telegram_id(db_session, 11021)
    user_id = user.id

    async def attempt() -> str:
        async with TestSessionLocal() as session:
            from app.models.user import User as UserModel
            from app.services.hero_service import get_active_hero
            from app.services.quest_service import claim_quest

            u = await session.get(UserModel, user_id)
            hero = await get_active_hero(session, u)
            try:
                await claim_quest(session, u, hero, user_quest_id)
                return "ok"
            except Exception as exc:
                return type(exc).__name__

    results = await asyncio.gather(attempt(), attempt())
    assert sorted(results) == ["ConflictError", "ok"]

    async with TestSessionLocal() as session:
        refreshed = await get_user_by_telegram_id(session, 11021)
        assert refreshed.balance == 10  # credited exactly once
