from pydantic import BaseModel


class BattleLogEntryOut(BaseModel):
    turn: int
    attacker: str
    target: str
    action_type: str
    skill_id: int | None
    damage: int
    critical: bool
    target_hp_after: int
    status_effects: list[dict]


class EnemySummaryOut(BaseModel):
    id: int
    name: str
    level: int


class BattleOut(BaseModel):
    id: int
    enemy: EnemySummaryOut
    result: str
    turns: int
    log: list[BattleLogEntryOut]
    reward_xp: int
    reward_coins: int
    hero_level: int
    hero_xp: int
    balance: int
    created_at: str


class StartBattleRequest(BaseModel):
    enemy_template_id: int
    idempotency_key: str | None = None
