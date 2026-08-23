from pydantic import BaseModel, ConfigDict


class SkillDefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    skill_type: str
    base_power: float
    power_per_skill_level: float
    cooldown_turns: int
    required_hero_level: int


class CharacterSkillOut(BaseModel):
    id: int
    level: int
    power: float
    skill_definition: SkillDefinitionOut


class AvailableSkillOut(BaseModel):
    skill_definition: SkillDefinitionOut
    is_unlocked: bool
    current_level: int  # 0 if not learned yet
    is_max_level: bool
    next_upgrade_cost: int | None  # None only when already at max level


class SkillBudgetOut(BaseModel):
    total: int
    spent: int
    available: int


class AvailableSkillsOut(BaseModel):
    budget: SkillBudgetOut
    skills: list[AvailableSkillOut]
