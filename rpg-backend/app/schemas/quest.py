from pydantic import BaseModel

from app.schemas.common import HeroProgressOut


class QuestOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    condition_type: str
    target_value: int
    current_progress: int
    is_completed: bool
    is_claimed: bool
    is_active_slot: bool
    reward_xp: int
    reward_coins: int


class QuestClaimOut(BaseModel):
    id: int
    code: str
    name: str
    reward_xp: int
    reward_coins: int
    claimed_at: str
    hero_progress: HeroProgressOut
