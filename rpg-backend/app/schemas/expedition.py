from pydantic import BaseModel


class ExpeditionTemplateOut(BaseModel):
    id: int
    name: str
    description: str | None
    image_path: str | None
    duration_seconds: int
    required_hero_level: int
    reward_xp: int
    reward_coins: int
    is_active: bool
    is_available_to_user: bool


class ExpeditionSummaryOut(BaseModel):
    id: int
    name: str


class UserExpeditionOut(BaseModel):
    id: int
    expedition: ExpeditionSummaryOut
    status: str  # "running" | "completed" | "claimed" — see ExpeditionStatus's docstring
    started_at: str
    completed_at: str
    claimed_at: str | None
    reward_xp: int
    reward_coins: int
    hero_level: int
    hero_xp: int
    balance: int
