from unittest.mock import patch

from tests.factories import create_class, create_hero_template, create_race
from tests.utils import telegram_headers

from app.services.minigame_service import DICE_MAX_ROLLS, DUMMY_ROUNDS, PAIRS_COUNT


async def _make_hero(client, db_session, telegram_id, bot_token):
    # Distinct Race/CharacterClass per call — create_hero_template's
    # defaults (code="human"/"warrior") collide the moment a single test
    # creates more than one hero (both codes are unique columns), which
    # test_memory_cannot_submit_someone_elses_attempt does.
    race = await create_race(db_session, code=f"race-{telegram_id}")
    char_class = await create_class(db_session, code=f"class-{telegram_id}")
    template = await create_hero_template(db_session, name=f"Герой{telegram_id}", race=race, char_class=char_class)
    await db_session.commit()
    headers = telegram_headers(telegram_id, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/heroes", headers=headers, json={"hero_template_id": template.id, "name": "Герой"})
    assert resp.status_code == 201
    return headers


# --- Memory Sequence -----------------------------------------------------

async def test_memory_start_returns_a_real_sequence(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9001, bot_token)

    resp = await client.post("/api/v1/minigames/memory/start", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["sequence"]) == 5
    assert all(0 <= i < len(body["symbols"]) for i in body["sequence"])


async def test_memory_correct_answer_grants_reward(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9002, bot_token)

    started = await client.post("/api/v1/minigames/memory/start", headers=headers)
    attempt_id, sequence = started.json()["attempt_id"], started.json()["sequence"]

    resp = await client.post(
        f"/api/v1/minigames/memory/{attempt_id}/submit", headers=headers, json={"answer": sequence}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["reward_xp"] > 0
    assert body["reward_coins"] > 0
    assert body["daily_rewarded_remaining"] == 4  # DAILY_REWARDED_LIMIT(5) - 1


async def test_memory_wrong_answer_grants_no_reward(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9003, bot_token)

    started = await client.post("/api/v1/minigames/memory/start", headers=headers)
    attempt_id, sequence = started.json()["attempt_id"], started.json()["sequence"]
    wrong = [(s + 1) % 5 for s in sequence]

    resp = await client.post(
        f"/api/v1/minigames/memory/{attempt_id}/submit", headers=headers, json={"answer": wrong}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["reward_xp"] == 0
    assert body["reward_coins"] == 0


async def test_memory_cannot_submit_twice(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9004, bot_token)

    started = await client.post("/api/v1/minigames/memory/start", headers=headers)
    attempt_id, sequence = started.json()["attempt_id"], started.json()["sequence"]

    first = await client.post(
        f"/api/v1/minigames/memory/{attempt_id}/submit", headers=headers, json={"answer": sequence}
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/minigames/memory/{attempt_id}/submit", headers=headers, json={"answer": sequence}
    )
    assert second.status_code == 409


async def test_memory_cannot_submit_someone_elses_attempt(client, db_session, bot_token):
    headers_a = await _make_hero(client, db_session, 9005, bot_token)
    headers_b = await _make_hero(client, db_session, 9006, bot_token)

    started = await client.post("/api/v1/minigames/memory/start", headers=headers_a)
    attempt_id = started.json()["attempt_id"]

    resp = await client.post(
        f"/api/v1/minigames/memory/{attempt_id}/submit", headers=headers_b, json={"answer": [0, 0, 0, 0, 0]}
    )
    assert resp.status_code == 403


async def test_memory_hourly_limit_enforced(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9007, bot_token)

    for _ in range(10):  # HOURLY_ATTEMPT_LIMIT
        resp = await client.post("/api/v1/minigames/memory/start", headers=headers)
        assert resp.status_code == 200

    over_limit = await client.post("/api/v1/minigames/memory/start", headers=headers)
    assert over_limit.status_code == 409


async def test_memory_daily_rewarded_cap_stops_rewards_but_not_play(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9008, bot_token)

    for _ in range(5):  # DAILY_REWARDED_LIMIT
        started = await client.post("/api/v1/minigames/memory/start", headers=headers)
        attempt_id, sequence = started.json()["attempt_id"], started.json()["sequence"]
        resp = await client.post(
            f"/api/v1/minigames/memory/{attempt_id}/submit", headers=headers, json={"answer": sequence}
        )
        assert resp.json()["reward_xp"] > 0

    started = await client.post("/api/v1/minigames/memory/start", headers=headers)
    attempt_id, sequence = started.json()["attempt_id"], started.json()["sequence"]
    resp = await client.post(
        f"/api/v1/minigames/memory/{attempt_id}/submit", headers=headers, json={"answer": sequence}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True  # still plays out correctly...
    assert body["reward_xp"] == 0  # ...just doesn't pay out anymore
    assert body["reward_coins"] == 0
    assert body["daily_rewarded_remaining"] == 0


async def test_memory_start_without_a_hero_is_404(client, bot_token):
    headers = telegram_headers(9009, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/minigames/memory/start", headers=headers)
    assert resp.status_code == 404


# --- Find the Pair ---------------------------------------------------------

async def test_pairs_start_returns_a_valid_shuffled_layout(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9010, bot_token)

    resp = await client.post("/api/v1/minigames/pairs/start", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["layout"]) == PAIRS_COUNT * 2
    for pair_id in range(PAIRS_COUNT):
        assert body["layout"].count(pair_id) == 2


async def test_pairs_perfect_moves_grants_full_reward(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9011, bot_token)

    started = await client.post("/api/v1/minigames/pairs/start", headers=headers)
    attempt_id = started.json()["attempt_id"]

    resp = await client.post(
        f"/api/v1/minigames/pairs/{attempt_id}/complete", headers=headers, json={"moves": PAIRS_COUNT}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["reward_xp"] == 20  # PAIRS_REWARD_XP, perfect tier == full
    assert body["reward_coins"] == 15  # PAIRS_REWARD_COINS


async def test_pairs_sloppy_moves_grants_reduced_reward(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9012, bot_token)

    started = await client.post("/api/v1/minigames/pairs/start", headers=headers)
    attempt_id = started.json()["attempt_id"]

    resp = await client.post(
        f"/api/v1/minigames/pairs/{attempt_id}/complete", headers=headers, json={"moves": PAIRS_COUNT * 5}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert 0 < body["reward_xp"] < 20  # sloppy tier: reduced, not zero


async def test_pairs_moves_below_minimum_is_clamped_not_trusted(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9013, bot_token)

    started = await client.post("/api/v1/minigames/pairs/start", headers=headers)
    attempt_id = started.json()["attempt_id"]

    # Claiming fewer moves than PAIRS_COUNT is impossible — server clamps
    # it up to PAIRS_COUNT rather than trusting an under-count, so this
    # still resolves as the (best-case) perfect tier, not an error.
    resp = await client.post(f"/api/v1/minigames/pairs/{attempt_id}/complete", headers=headers, json={"moves": 1})
    assert resp.status_code == 200
    assert resp.json()["reward_xp"] == 20


async def test_pairs_start_without_a_hero_is_404(client, bot_token):
    headers = telegram_headers(9014, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/minigames/pairs/start", headers=headers)
    assert resp.status_code == 404


# --- Training Dummy ---------------------------------------------------------

async def test_dummy_start_returns_directions(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9015, bot_token)
    resp = await client.post("/api/v1/minigames/dummy/start", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["directions"]) == DUMMY_ROUNDS
    assert all(d in ("left", "right", "up", "down") for d in body["directions"])


async def test_dummy_perfect_hits_grants_full_reward(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9016, bot_token)
    started = await client.post("/api/v1/minigames/dummy/start", headers=headers)
    attempt_id = started.json()["attempt_id"]
    resp = await client.post(
        f"/api/v1/minigames/dummy/{attempt_id}/complete", headers=headers, json={"hits": DUMMY_ROUNDS}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["reward_xp"] == 15


async def test_dummy_zero_hits_grants_no_reward(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9017, bot_token)
    started = await client.post("/api/v1/minigames/dummy/start", headers=headers)
    attempt_id = started.json()["attempt_id"]
    resp = await client.post(f"/api/v1/minigames/dummy/{attempt_id}/complete", headers=headers, json={"hits": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["reward_xp"] == 0
    assert body["reward_coins"] == 0


async def test_dummy_hits_above_rounds_is_clamped_not_trusted(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9018, bot_token)
    started = await client.post("/api/v1/minigames/dummy/start", headers=headers)
    attempt_id = started.json()["attempt_id"]
    resp = await client.post(
        f"/api/v1/minigames/dummy/{attempt_id}/complete", headers=headers, json={"hits": 999}
    )
    assert resp.status_code == 200
    assert resp.json()["reward_xp"] == 15  # clamped to DUMMY_ROUNDS -> still just the perfect tier


async def test_dummy_start_without_a_hero_is_404(client, bot_token):
    headers = telegram_headers(9019, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/minigames/dummy/start", headers=headers)
    assert resp.status_code == 404


# --- Alchemy -----------------------------------------------------------------

async def test_alchemy_start_returns_a_permutation_recipe(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9020, bot_token)
    resp = await client.post("/api/v1/minigames/alchemy/start", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert sorted(body["recipe"]) == list(range(len(body["ingredients"])))


async def test_alchemy_correct_order_grants_reward(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9021, bot_token)
    started = await client.post("/api/v1/minigames/alchemy/start", headers=headers)
    attempt_id, recipe = started.json()["attempt_id"], started.json()["recipe"]
    resp = await client.post(
        f"/api/v1/minigames/alchemy/{attempt_id}/submit", headers=headers, json={"answer": recipe}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["reward_xp"] == 18
    assert body["reward_coins"] == 12


async def test_alchemy_wrong_order_grants_no_reward(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9022, bot_token)
    started = await client.post("/api/v1/minigames/alchemy/start", headers=headers)
    attempt_id, recipe = started.json()["attempt_id"], started.json()["recipe"]
    wrong = list(reversed(recipe)) if recipe != list(reversed(recipe)) else recipe[1:] + recipe[:1]
    resp = await client.post(
        f"/api/v1/minigames/alchemy/{attempt_id}/submit", headers=headers, json={"answer": wrong}
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is False


async def test_alchemy_start_without_a_hero_is_404(client, bot_token):
    headers = telegram_headers(9023, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/minigames/alchemy/start", headers=headers)
    assert resp.status_code == 404


# --- Tavern Dice (push-your-luck) --------------------------------------------

async def test_dice_start_returns_zero_pot(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9024, bot_token)
    resp = await client.post("/api/v1/minigames/dice/start", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["pot"] == 0
    assert body["finished"] is False


async def test_dice_roll_adds_to_pot_when_not_busted(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9025, bot_token)
    started = await client.post("/api/v1/minigames/dice/start", headers=headers)
    attempt_id = started.json()["attempt_id"]

    with patch("app.services.minigame_service.random.randint", return_value=4):
        resp = await client.post(f"/api/v1/minigames/dice/{attempt_id}/roll", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["busted"] is False
    assert body["pot"] == 4
    assert body["finished"] is False


async def test_dice_roll_busts_and_ends_attempt_with_no_reward(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9026, bot_token)
    started = await client.post("/api/v1/minigames/dice/start", headers=headers)
    attempt_id = started.json()["attempt_id"]

    with patch("app.services.minigame_service.random.randint", return_value=1):
        resp = await client.post(f"/api/v1/minigames/dice/{attempt_id}/roll", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["busted"] is True
    assert body["finished"] is True
    assert body["pot"] == 0
    assert body["reward_xp"] == 0
    assert body["reward_coins"] == 0

    # attempt is resolved — rolling again must fail
    again = await client.post(f"/api/v1/minigames/dice/{attempt_id}/roll", headers=headers)
    assert again.status_code == 409


async def test_dice_bank_grants_reward_based_on_pot(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9027, bot_token)
    started = await client.post("/api/v1/minigames/dice/start", headers=headers)
    attempt_id = started.json()["attempt_id"]

    with patch("app.services.minigame_service.random.randint", return_value=5):
        await client.post(f"/api/v1/minigames/dice/{attempt_id}/roll", headers=headers)
        rolled_again = await client.post(f"/api/v1/minigames/dice/{attempt_id}/roll", headers=headers)
    assert rolled_again.json()["pot"] == 10

    banked = await client.post(f"/api/v1/minigames/dice/{attempt_id}/bank", headers=headers)
    assert banked.status_code == 200
    body = banked.json()
    assert body["finished"] is True
    assert body["pot"] == 10
    assert body["reward_coins"] == 10  # DICE_COIN_PER_POT == 1.0
    assert body["reward_xp"] == round(10 * 0.75)


async def test_dice_hits_max_rolls_auto_finishes(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9028, bot_token)
    started = await client.post("/api/v1/minigames/dice/start", headers=headers)
    attempt_id = started.json()["attempt_id"]

    with patch("app.services.minigame_service.random.randint", return_value=2):
        last = None
        for _ in range(DICE_MAX_ROLLS):
            last = await client.post(f"/api/v1/minigames/dice/{attempt_id}/roll", headers=headers)
    assert last.json()["finished"] is True
    assert last.json()["rolls_made"] == DICE_MAX_ROLLS


async def test_dice_start_without_a_hero_is_404(client, bot_token):
    headers = telegram_headers(9029, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/minigames/dice/start", headers=headers)
    assert resp.status_code == 404


# --- Three Cups (shell game) -------------------------------------------------

async def test_cups_start_returns_round_one(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9030, bot_token)
    resp = await client.post("/api/v1/minigames/cups/start", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["round"] == 1
    assert body["finished"] is False


async def test_cups_correct_guess_advances_round(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9031, bot_token)
    with patch("app.services.minigame_service.random.randint", return_value=1):
        started = await client.post("/api/v1/minigames/cups/start", headers=headers)
        attempt_id = started.json()["attempt_id"]
        resp = await client.post(f"/api/v1/minigames/cups/{attempt_id}/guess", headers=headers, json={"cup": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["correct"] is True
    assert body["finished"] is False
    assert body["round"] == 2


async def test_cups_wrong_guess_ends_attempt_with_no_reward(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9032, bot_token)
    with patch("app.services.minigame_service.random.randint", return_value=1):
        started = await client.post("/api/v1/minigames/cups/start", headers=headers)
        attempt_id = started.json()["attempt_id"]
        resp = await client.post(f"/api/v1/minigames/cups/{attempt_id}/guess", headers=headers, json={"cup": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["correct"] is False
    assert body["finished"] is True
    assert body["reward_xp"] == 0
    assert body["reward_coins"] == 0


async def test_cups_clearing_max_rounds_grants_full_reward(client, db_session, bot_token):
    headers = await _make_hero(client, db_session, 9033, bot_token)
    with patch("app.services.minigame_service.random.randint", return_value=1):
        started = await client.post("/api/v1/minigames/cups/start", headers=headers)
        attempt_id = started.json()["attempt_id"]
        last = None
        for _ in range(5):  # CUPS_MAX_ROUNDS
            last = await client.post(f"/api/v1/minigames/cups/{attempt_id}/guess", headers=headers, json={"cup": 1})
    body = last.json()
    assert body["finished"] is True
    assert body["correct"] is True
    assert body["reward_xp"] == 6 * 5  # CUPS_REWARD_XP_PER_ROUND * rounds cleared
    assert body["reward_coins"] == 4 * 5


async def test_cups_start_without_a_hero_is_404(client, bot_token):
    headers = telegram_headers(9034, bot_token)
    await client.post("/api/v1/auth/session", headers=headers)
    resp = await client.post("/api/v1/minigames/cups/start", headers=headers)
    assert resp.status_code == 404
