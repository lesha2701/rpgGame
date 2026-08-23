from pydantic import BaseModel, Field

from app.schemas.common import HeroProgressOut


class MemoryStartOut(BaseModel):
    attempt_id: int
    sequence: list[int]
    symbols: list[str]


class MemorySubmitRequest(BaseModel):
    answer: list[int]


class PairsStartOut(BaseModel):
    attempt_id: int
    layout: list[int]
    symbols: list[str]


class PairsCompleteRequest(BaseModel):
    moves: int = Field(ge=1)


class MinigameResultOut(BaseModel):
    success: bool
    reward_xp: int
    reward_coins: int
    daily_rewarded_remaining: int
    hero_progress: HeroProgressOut


class DummyStartOut(BaseModel):
    attempt_id: int
    directions: list[str]


class DummyCompleteRequest(BaseModel):
    hits: int = Field(ge=0)


class AlchemyStartOut(BaseModel):
    attempt_id: int
    recipe: list[int]
    ingredients: list[str]


class AlchemySubmitRequest(BaseModel):
    answer: list[int]


class DiceRoundOut(BaseModel):
    """Shared shape for start/roll/bank — `roll` is null for start (no dice
    thrown yet) and for bank (banking doesn't throw). `finished` is true
    once the attempt is resolved (busted, banked, or hit max_rolls), at
    which point reward_xp/reward_coins reflect the payout; while still in
    progress they're always 0 and hero_progress is just the current
    (unchanged) snapshot."""

    attempt_id: int
    roll: int | None
    busted: bool
    pot: int
    rolls_made: int
    max_rolls: int
    finished: bool
    reward_xp: int
    reward_coins: int
    daily_rewarded_remaining: int
    hero_progress: HeroProgressOut


class CupsGuessRequest(BaseModel):
    cup: int = Field(ge=0, le=2)


class CupsRoundOut(BaseModel):
    """Shared shape for start/guess — `correct` is null for start (no
    guess made yet). `finished` is true once the attempt is resolved (a
    wrong guess, or clearing max_rounds), at which point reward_xp/
    reward_coins reflect the payout; while still in progress they're
    always 0."""

    attempt_id: int
    correct: bool | None
    round: int
    max_rounds: int
    finished: bool
    reward_xp: int
    reward_coins: int
    daily_rewarded_remaining: int
    hero_progress: HeroProgressOut
