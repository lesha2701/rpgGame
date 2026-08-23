"""Shared hourly/daily attempt gating for mini-games — one implementation
parametrized by which pair of column-name-pairs a given game uses, instead
of Memory Sequence and Find the Pair each hand-rolling the same rolling-
window logic. See User model's docstring for the four columns each game
has and why.

Not a copy of anything in the football sibling app — this is RPG's own
fresh implementation of the same shape of problem (rolling-hour attempt
cap, rolling-day rewarded-attempt cap), built against RPG's own User
model and ConflictError, because RPG had no such mechanism at all before
this pass (every other RPG system uses a different gate: chests are
coin-gated, expeditions are one-active-at-a-time, quests are one-time)."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.exceptions import ConflictError
from app.core.timeutil import ensure_aware
from app.models.user import User

HOURLY_ATTEMPT_LIMIT = 10
DAILY_REWARDED_LIMIT = 5
_HOUR = timedelta(hours=1)
_DAY = timedelta(hours=24)


@dataclass(frozen=True)
class MinigameLimitFields:
    hourly_attempts: str
    hour_started_at: str
    rewarded_attempts_today: str
    attempts_reset_at: str


MEMORY_LIMIT_FIELDS = MinigameLimitFields(
    "memory_hourly_attempts", "memory_hour_started_at", "memory_rewarded_attempts_today", "memory_attempts_reset_at"
)
PAIRS_LIMIT_FIELDS = MinigameLimitFields(
    "pairs_hourly_attempts", "pairs_hour_started_at", "pairs_rewarded_attempts_today", "pairs_attempts_reset_at"
)
DUMMY_LIMIT_FIELDS = MinigameLimitFields(
    "dummy_hourly_attempts", "dummy_hour_started_at", "dummy_rewarded_attempts_today", "dummy_attempts_reset_at"
)
ALCHEMY_LIMIT_FIELDS = MinigameLimitFields(
    "alchemy_hourly_attempts", "alchemy_hour_started_at", "alchemy_rewarded_attempts_today", "alchemy_attempts_reset_at"
)
DICE_LIMIT_FIELDS = MinigameLimitFields(
    "dice_hourly_attempts", "dice_hour_started_at", "dice_rewarded_attempts_today", "dice_attempts_reset_at"
)
CUPS_LIMIT_FIELDS = MinigameLimitFields(
    "cups_hourly_attempts", "cups_hour_started_at", "cups_rewarded_attempts_today", "cups_attempts_reset_at"
)


def consume_hourly_attempt(user: User, fields: MinigameLimitFields) -> None:
    """Call once per `start` — raises ConflictError if the hourly cap is
    already spent, otherwise rolls the window forward if it has expired
    and increments the counter. Mutates `user` in place; the caller is
    responsible for `db.add(user)` + commit, same contract as every other
    in-place User mutation in this codebase (credit_coins, etc.)."""
    now = datetime.now(timezone.utc)
    started_at = getattr(user, fields.hour_started_at)
    if started_at is None or ensure_aware(started_at) + _HOUR <= now:
        setattr(user, fields.hour_started_at, now)
        setattr(user, fields.hourly_attempts, 0)

    attempts = getattr(user, fields.hourly_attempts)
    if attempts >= HOURLY_ATTEMPT_LIMIT:
        next_reset = ensure_aware(getattr(user, fields.hour_started_at)) + _HOUR
        raise ConflictError(
            "Hourly attempt limit reached for this mini-game",
            details={"limit": HOURLY_ATTEMPT_LIMIT, "next_available_at": next_reset.isoformat()},
        )
    setattr(user, fields.hourly_attempts, attempts + 1)


def rewarded_attempts_remaining(user: User, fields: MinigameLimitFields) -> int:
    """Rolls the daily window forward if expired, then reports how many
    rewarded attempts are left today — 0 means the attempt still plays
    out normally, it just won't grant xp/coins (see MinigameAttempt's
    docstring: this is a reward cap, not a play cap)."""
    now = datetime.now(timezone.utc)
    reset_at = getattr(user, fields.attempts_reset_at)
    if reset_at is None or ensure_aware(reset_at) <= now:
        setattr(user, fields.attempts_reset_at, now + _DAY)
        setattr(user, fields.rewarded_attempts_today, 0)
    return DAILY_REWARDED_LIMIT - getattr(user, fields.rewarded_attempts_today)


def consume_rewarded_attempt(user: User, fields: MinigameLimitFields) -> None:
    setattr(user, fields.rewarded_attempts_today, getattr(user, fields.rewarded_attempts_today) + 1)
