"""Six mini-games under the restructured Battle hub (Arena/PvE/mini-games
all live under one tab now, frontend-side): Memory Sequence, Find the
Pair, Training Dummy, Alchemy, Tavern Dice, Three Cups.

Four share one start/resolve shape: `start` generates a server-side
secret (a random sequence / a shuffled pair layout / a prompt list),
persists it on a MinigameAttempt row so scoring at submit/complete time
checks the real answer instead of trusting the client, and resolves in
exactly one follow-up call. Tavern Dice and Three Cups are genuinely
multi-step instead — each `roll`/`guess` call mutates the same still-
`pending` attempt row until it busts, banks, or clears every round.

Every game's reward-grant goes through reward_service.grant_hero_reward —
same "lock user, grant_xp, credit_coins" composition every other reward
path in this app already uses — gated by _apply_daily_cap (shared here so
six games don't each hand-roll the same "zero it out once the daily cap
is spent" branch). Reward amounts are plain module constants, the same
precedent Arena's ARENA_WIN_REWARD_XP/COINS already set for a non-template
game mode (Enemy/Expedition/Quest rewards live on their own admin-editable
template rows; these mini-games have no template row to put them on)."""

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.enums import MinigameAttemptStatus, MinigameType, TransactionType
from app.models.minigame_attempt import MinigameAttempt
from app.models.user import User
from app.models.user_hero import UserHero
from app.schemas.common import HeroProgressOut
from app.schemas.minigame import (
    AlchemyStartOut,
    CupsRoundOut,
    DiceRoundOut,
    DummyStartOut,
    MemoryStartOut,
    MinigameResultOut,
    PairsStartOut,
)
from app.services.hero_service import hero_progress_out
from app.services.minigame_limits_service import (
    ALCHEMY_LIMIT_FIELDS,
    CUPS_LIMIT_FIELDS,
    DICE_LIMIT_FIELDS,
    DUMMY_LIMIT_FIELDS,
    MEMORY_LIMIT_FIELDS,
    PAIRS_LIMIT_FIELDS,
    MinigameLimitFields,
    consume_hourly_attempt,
    consume_rewarded_attempt,
    rewarded_attempts_remaining,
)
from app.services.reward_service import grant_hero_reward

SYMBOLS = ["🔥", "💧", "🌿", "💨", "⚡", "❄️", "🌑", "☀️"]

MEMORY_SEQUENCE_LENGTH = 5
MEMORY_REWARD_XP = 15
MEMORY_REWARD_COINS = 10

PAIRS_COUNT = 6
PAIRS_REWARD_XP = 20
PAIRS_REWARD_COINS = 15
# Move-count efficiency tiers: a perfect run is exactly PAIRS_COUNT moves
# (one flip-pair per match, no misses) — realistically achievable only by
# memorizing the layout perfectly. Reward scales down as moves grow past
# that, never invented to be harsh: even a sloppy 3x-moves clear still
# grants a quarter of the base reward.
_PAIRS_GOOD_MOVES = PAIRS_COUNT * 2
_PAIRS_TIER_SCALE = {"perfect": 1.0, "good": 0.6, "sloppy": 0.25}

DIRECTIONS = ["left", "right", "up", "down"]
DUMMY_ROUNDS = 8
DUMMY_REWARD_XP = 15
DUMMY_REWARD_COINS = 10
_DUMMY_GOOD_HITS = round(DUMMY_ROUNDS * 0.75)
_DUMMY_TIER_SCALE = {"perfect": 1.0, "good": 0.6, "sloppy": 0.25}

ALCHEMY_INGREDIENTS = ["🌿", "🍄", "🦴", "💎", "🔥", "💧"]
ALCHEMY_REWARD_XP = 18
ALCHEMY_REWARD_COINS = 12

# Tavern Dice: 1/6 bust chance per roll (rolling a 1), otherwise the roll
# value (2-6) adds to the pot. A soft cap on rolls forces eventual
# resolution instead of an unbounded push-your-luck loop.
DICE_MAX_ROLLS = 10
DICE_BUST_VALUE = 1
DICE_COIN_PER_POT = 1.0
DICE_XP_PER_POT = 0.75

CUPS_MAX_ROUNDS = 5
CUPS_REWARD_XP_PER_ROUND = 6
CUPS_REWARD_COINS_PER_ROUND = 4


async def _get_hero_or_404(hero: UserHero | None) -> UserHero:
    if hero is None:
        raise NotFoundError("You don't have a hero yet")
    return hero


async def _lock_owned_pending_attempt(
    db: AsyncSession, user_id: int, attempt_id: int, game_type: MinigameType
) -> MinigameAttempt:
    # No `of=` scoping needed — MinigameAttempt declares no relationships
    # (same reasoning as ArenaMatch's own docstring), so a plain
    # with_for_update() is unambiguous here.
    result = await db.execute(
        select(MinigameAttempt).where(MinigameAttempt.id == attempt_id).with_for_update()
    )
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise NotFoundError("Attempt not found")
    if attempt.user_id != user_id:
        raise ForbiddenError("This attempt does not belong to you")
    if attempt.game_type != game_type:
        raise NotFoundError("Attempt not found")
    if attempt.status != MinigameAttemptStatus.pending:
        raise ConflictError("This attempt has already been resolved")
    return attempt


def _apply_daily_cap(user: User, fields: MinigameLimitFields, xp: int, coins: int) -> tuple[int, int, int]:
    """Rolls the daily rewarded-attempt window forward, then either
    consumes one slot (if the computed reward is non-zero and slots
    remain) or zeroes the reward out (cap already spent). Returns
    (xp, coins, remaining_after)."""
    remaining = rewarded_attempts_remaining(user, fields)
    if xp or coins:
        if remaining <= 0:
            xp, coins = 0, 0
        else:
            consume_rewarded_attempt(user, fields)
            remaining -= 1
    return xp, coins, max(0, remaining)


async def start_memory(db: AsyncSession, user: User, hero: UserHero | None) -> MemoryStartOut:
    await _get_hero_or_404(hero)
    consume_hourly_attempt(user, MEMORY_LIMIT_FIELDS)

    memory_symbols = SYMBOLS[:5]
    sequence = [random.randrange(len(memory_symbols)) for _ in range(MEMORY_SEQUENCE_LENGTH)]
    attempt = MinigameAttempt(
        user_id=user.id, game_type=MinigameType.memory, payload={"sequence": sequence}
    )
    db.add(attempt)
    db.add(user)
    await db.flush()
    await db.commit()

    return MemoryStartOut(attempt_id=attempt.id, sequence=sequence, symbols=memory_symbols)


async def submit_memory(
    db: AsyncSession, user: User, hero: UserHero | None, attempt_id: int, answer: list[int]
) -> MinigameResultOut:
    hero = await _get_hero_or_404(hero)
    attempt = await _lock_owned_pending_attempt(db, user.id, attempt_id, MinigameType.memory)

    success = answer == attempt.payload["sequence"]
    xp, coins = (MEMORY_REWARD_XP, MEMORY_REWARD_COINS) if success else (0, 0)
    xp, coins, remaining = _apply_daily_cap(user, MEMORY_LIMIT_FIELDS, xp, coins)

    attempt.status = MinigameAttemptStatus.completed
    attempt.reward_xp = xp
    attempt.reward_coins = coins
    db.add(attempt)

    locked_hero, locked_user = await grant_hero_reward(
        db, hero.id, user.id, xp, coins, TransactionType.minigame_reward, "Запомни последовательность"
    )
    await db.commit()

    return MinigameResultOut(
        success=success,
        reward_xp=xp,
        reward_coins=coins,
        daily_rewarded_remaining=remaining,
        hero_progress=hero_progress_out(locked_hero, locked_user),
    )


async def start_pairs(db: AsyncSession, user: User, hero: UserHero | None) -> PairsStartOut:
    await _get_hero_or_404(hero)
    consume_hourly_attempt(user, PAIRS_LIMIT_FIELDS)

    pair_symbols = SYMBOLS[:PAIRS_COUNT]
    layout = list(range(PAIRS_COUNT)) * 2
    random.shuffle(layout)

    attempt = MinigameAttempt(user_id=user.id, game_type=MinigameType.pairs, payload={"layout": layout})
    db.add(attempt)
    db.add(user)
    await db.flush()
    await db.commit()

    return PairsStartOut(attempt_id=attempt.id, layout=layout, symbols=pair_symbols)


def _pairs_reward_scale(moves: int) -> float:
    if moves <= PAIRS_COUNT:
        return _PAIRS_TIER_SCALE["perfect"]
    if moves <= _PAIRS_GOOD_MOVES:
        return _PAIRS_TIER_SCALE["good"]
    return _PAIRS_TIER_SCALE["sloppy"]


async def complete_pairs(
    db: AsyncSession, user: User, hero: UserHero | None, attempt_id: int, moves: int
) -> MinigameResultOut:
    hero = await _get_hero_or_404(hero)
    attempt = await _lock_owned_pending_attempt(db, user.id, attempt_id, MinigameType.pairs)

    # A completed grid can never take fewer than PAIRS_COUNT moves (one
    # flip-pair per match, best case) — clamp rather than trust a
    # suspiciously low client-reported count.
    moves = max(moves, PAIRS_COUNT)
    scale = _pairs_reward_scale(moves)
    xp = round(PAIRS_REWARD_XP * scale)
    coins = round(PAIRS_REWARD_COINS * scale)
    xp, coins, remaining = _apply_daily_cap(user, PAIRS_LIMIT_FIELDS, xp, coins)

    attempt.status = MinigameAttemptStatus.completed
    attempt.reward_xp = xp
    attempt.reward_coins = coins
    db.add(attempt)

    locked_hero, locked_user = await grant_hero_reward(
        db, hero.id, user.id, xp, coins, TransactionType.minigame_reward, "Найди пару"
    )
    await db.commit()

    return MinigameResultOut(
        success=True,
        reward_xp=xp,
        reward_coins=coins,
        daily_rewarded_remaining=remaining,
        hero_progress=hero_progress_out(locked_hero, locked_user),
    )


# --- Training Dummy (reaction test) -----------------------------------------


def _dummy_reward_scale(hits: int) -> float:
    if hits >= DUMMY_ROUNDS:
        return _DUMMY_TIER_SCALE["perfect"]
    if hits >= _DUMMY_GOOD_HITS:
        return _DUMMY_TIER_SCALE["good"]
    if hits > 0:
        return _DUMMY_TIER_SCALE["sloppy"]
    return 0.0


async def start_dummy(db: AsyncSession, user: User, hero: UserHero | None) -> DummyStartOut:
    await _get_hero_or_404(hero)
    consume_hourly_attempt(user, DUMMY_LIMIT_FIELDS)

    directions = [random.choice(DIRECTIONS) for _ in range(DUMMY_ROUNDS)]
    attempt = MinigameAttempt(user_id=user.id, game_type=MinigameType.dummy, payload={"directions": directions})
    db.add(attempt)
    db.add(user)
    await db.flush()
    await db.commit()

    return DummyStartOut(attempt_id=attempt.id, directions=directions)


async def complete_dummy(
    db: AsyncSession, user: User, hero: UserHero | None, attempt_id: int, hits: int
) -> MinigameResultOut:
    hero = await _get_hero_or_404(hero)
    attempt = await _lock_owned_pending_attempt(db, user.id, attempt_id, MinigameType.dummy)

    # Can't have hit more prompts than actually appeared — clamp rather
    # than trust an inflated client-reported count.
    hits = min(hits, DUMMY_ROUNDS)
    scale = _dummy_reward_scale(hits)
    xp = round(DUMMY_REWARD_XP * scale)
    coins = round(DUMMY_REWARD_COINS * scale)
    xp, coins, remaining = _apply_daily_cap(user, DUMMY_LIMIT_FIELDS, xp, coins)

    attempt.status = MinigameAttemptStatus.completed
    attempt.reward_xp = xp
    attempt.reward_coins = coins
    db.add(attempt)

    locked_hero, locked_user = await grant_hero_reward(
        db, hero.id, user.id, xp, coins, TransactionType.minigame_reward, "Боевой манекен"
    )
    await db.commit()

    return MinigameResultOut(
        success=hits == DUMMY_ROUNDS,
        reward_xp=xp,
        reward_coins=coins,
        daily_rewarded_remaining=remaining,
        hero_progress=hero_progress_out(locked_hero, locked_user),
    )


# --- Alchemy (recipe ordering) ----------------------------------------------


async def start_alchemy(db: AsyncSession, user: User, hero: UserHero | None) -> AlchemyStartOut:
    await _get_hero_or_404(hero)
    consume_hourly_attempt(user, ALCHEMY_LIMIT_FIELDS)

    recipe = list(range(len(ALCHEMY_INGREDIENTS)))
    random.shuffle(recipe)
    attempt = MinigameAttempt(user_id=user.id, game_type=MinigameType.alchemy, payload={"recipe": recipe})
    db.add(attempt)
    db.add(user)
    await db.flush()
    await db.commit()

    return AlchemyStartOut(attempt_id=attempt.id, recipe=recipe, ingredients=ALCHEMY_INGREDIENTS)


async def submit_alchemy(
    db: AsyncSession, user: User, hero: UserHero | None, attempt_id: int, answer: list[int]
) -> MinigameResultOut:
    hero = await _get_hero_or_404(hero)
    attempt = await _lock_owned_pending_attempt(db, user.id, attempt_id, MinigameType.alchemy)

    success = answer == attempt.payload["recipe"]
    xp, coins = (ALCHEMY_REWARD_XP, ALCHEMY_REWARD_COINS) if success else (0, 0)
    xp, coins, remaining = _apply_daily_cap(user, ALCHEMY_LIMIT_FIELDS, xp, coins)

    attempt.status = MinigameAttemptStatus.completed
    attempt.reward_xp = xp
    attempt.reward_coins = coins
    db.add(attempt)

    locked_hero, locked_user = await grant_hero_reward(
        db, hero.id, user.id, xp, coins, TransactionType.minigame_reward, "Алхимия"
    )
    await db.commit()

    return MinigameResultOut(
        success=success,
        reward_xp=xp,
        reward_coins=coins,
        daily_rewarded_remaining=remaining,
        hero_progress=hero_progress_out(locked_hero, locked_user),
    )


# --- Tavern Dice (push-your-luck) -------------------------------------------


def _dice_round_out(
    attempt: MinigameAttempt,
    roll: int | None,
    busted: bool,
    finished: bool,
    reward_xp: int,
    reward_coins: int,
    daily_rewarded_remaining: int,
    hero_progress: HeroProgressOut,
) -> DiceRoundOut:
    return DiceRoundOut(
        attempt_id=attempt.id,
        roll=roll,
        busted=busted,
        pot=attempt.payload["pot"],
        rolls_made=attempt.payload["rolls_made"],
        max_rolls=DICE_MAX_ROLLS,
        finished=finished,
        reward_xp=reward_xp,
        reward_coins=reward_coins,
        daily_rewarded_remaining=daily_rewarded_remaining,
        hero_progress=hero_progress,
    )


async def start_dice(db: AsyncSession, user: User, hero: UserHero | None) -> DiceRoundOut:
    hero = await _get_hero_or_404(hero)
    consume_hourly_attempt(user, DICE_LIMIT_FIELDS)

    attempt = MinigameAttempt(user_id=user.id, game_type=MinigameType.dice, payload={"pot": 0, "rolls_made": 0})
    db.add(attempt)
    db.add(user)
    await db.flush()
    await db.commit()

    remaining = rewarded_attempts_remaining(user, DICE_LIMIT_FIELDS)
    return _dice_round_out(attempt, None, False, False, 0, 0, remaining, hero_progress_out(hero, user))


async def _finish_dice(
    db: AsyncSession, user: User, hero: UserHero, attempt: MinigameAttempt, roll: int | None, busted: bool
) -> DiceRoundOut:
    pot = 0 if busted else attempt.payload["pot"]
    xp = round(pot * DICE_XP_PER_POT)
    coins = round(pot * DICE_COIN_PER_POT)
    xp, coins, remaining = _apply_daily_cap(user, DICE_LIMIT_FIELDS, xp, coins)

    attempt.status = MinigameAttemptStatus.completed
    attempt.reward_xp = xp
    attempt.reward_coins = coins
    db.add(attempt)

    locked_hero, locked_user = await grant_hero_reward(
        db, hero.id, user.id, xp, coins, TransactionType.minigame_reward, "Тавернные кости"
    )
    await db.commit()

    return _dice_round_out(attempt, roll, busted, True, xp, coins, remaining, hero_progress_out(locked_hero, locked_user))


async def roll_dice(db: AsyncSession, user: User, hero: UserHero | None, attempt_id: int) -> DiceRoundOut:
    hero = await _get_hero_or_404(hero)
    attempt = await _lock_owned_pending_attempt(db, user.id, attempt_id, MinigameType.dice)

    roll = random.randint(1, 6)
    if roll == DICE_BUST_VALUE:
        return await _finish_dice(db, user, hero, attempt, roll, busted=True)

    attempt.payload = {**attempt.payload, "pot": attempt.payload["pot"] + roll, "rolls_made": attempt.payload["rolls_made"] + 1}
    if attempt.payload["rolls_made"] >= DICE_MAX_ROLLS:
        db.add(attempt)
        await db.flush()
        return await _finish_dice(db, user, hero, attempt, roll, busted=False)

    db.add(attempt)
    await db.commit()
    remaining = rewarded_attempts_remaining(user, DICE_LIMIT_FIELDS)
    return _dice_round_out(attempt, roll, False, False, 0, 0, remaining, hero_progress_out(hero, user))


async def bank_dice(db: AsyncSession, user: User, hero: UserHero | None, attempt_id: int) -> DiceRoundOut:
    hero = await _get_hero_or_404(hero)
    attempt = await _lock_owned_pending_attempt(db, user.id, attempt_id, MinigameType.dice)
    return await _finish_dice(db, user, hero, attempt, None, busted=False)


# --- Three Cups (shell game) -------------------------------------------------


def _cups_round_out(
    attempt: MinigameAttempt,
    correct: bool | None,
    finished: bool,
    reward_xp: int,
    reward_coins: int,
    daily_rewarded_remaining: int,
    hero_progress: HeroProgressOut,
) -> CupsRoundOut:
    return CupsRoundOut(
        attempt_id=attempt.id,
        correct=correct,
        round=attempt.payload["round"],
        max_rounds=CUPS_MAX_ROUNDS,
        finished=finished,
        reward_xp=reward_xp,
        reward_coins=reward_coins,
        daily_rewarded_remaining=daily_rewarded_remaining,
        hero_progress=hero_progress,
    )


async def start_cups(db: AsyncSession, user: User, hero: UserHero | None) -> CupsRoundOut:
    hero = await _get_hero_or_404(hero)
    consume_hourly_attempt(user, CUPS_LIMIT_FIELDS)

    attempt = MinigameAttempt(
        user_id=user.id, game_type=MinigameType.cups, payload={"round": 1, "correct_cup": random.randint(0, 2)}
    )
    db.add(attempt)
    db.add(user)
    await db.flush()
    await db.commit()

    remaining = rewarded_attempts_remaining(user, CUPS_LIMIT_FIELDS)
    return _cups_round_out(attempt, None, False, 0, 0, remaining, hero_progress_out(hero, user))


async def guess_cups(db: AsyncSession, user: User, hero: UserHero | None, attempt_id: int, cup: int) -> CupsRoundOut:
    hero = await _get_hero_or_404(hero)
    attempt = await _lock_owned_pending_attempt(db, user.id, attempt_id, MinigameType.cups)

    correct = cup == attempt.payload["correct_cup"]
    cleared_round = attempt.payload["round"]

    if not correct:
        xp, coins = 0, 0
        xp, coins, remaining = _apply_daily_cap(user, CUPS_LIMIT_FIELDS, xp, coins)
        attempt.status = MinigameAttemptStatus.completed
        attempt.reward_xp, attempt.reward_coins = xp, coins
        db.add(attempt)
        locked_hero, locked_user = await grant_hero_reward(
            db, hero.id, user.id, xp, coins, TransactionType.minigame_reward, "Три кубка"
        )
        await db.commit()
        return _cups_round_out(attempt, False, True, xp, coins, remaining, hero_progress_out(locked_hero, locked_user))

    if cleared_round >= CUPS_MAX_ROUNDS:
        xp = CUPS_REWARD_XP_PER_ROUND * cleared_round
        coins = CUPS_REWARD_COINS_PER_ROUND * cleared_round
        xp, coins, remaining = _apply_daily_cap(user, CUPS_LIMIT_FIELDS, xp, coins)
        attempt.status = MinigameAttemptStatus.completed
        attempt.reward_xp, attempt.reward_coins = xp, coins
        db.add(attempt)
        locked_hero, locked_user = await grant_hero_reward(
            db, hero.id, user.id, xp, coins, TransactionType.minigame_reward, "Три кубка"
        )
        await db.commit()
        return _cups_round_out(attempt, True, True, xp, coins, remaining, hero_progress_out(locked_hero, locked_user))

    attempt.payload = {"round": cleared_round + 1, "correct_cup": random.randint(0, 2)}
    db.add(attempt)
    await db.commit()
    remaining = rewarded_attempts_remaining(user, CUPS_LIMIT_FIELDS)
    return _cups_round_out(attempt, True, False, 0, 0, remaining, hero_progress_out(hero, user))
