from pydantic import BaseModel


class EnemyOut(BaseModel):
    id: int
    name: str
    description: str | None
    image_path: str | None
    level: int
    hp: int
    attack: int
    defense: int
    speed: int
    crit_chance: float
    crit_damage: float
    reward_xp: int
    reward_coins: int
    is_available_to_user: bool
