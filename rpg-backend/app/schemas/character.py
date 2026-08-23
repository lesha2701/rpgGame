from pydantic import BaseModel, ConfigDict, Field, field_validator


class RaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    image_path: str | None


class CharacterClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    image_path: str | None
    base_hp: int
    base_attack: int
    base_defense: int
    base_speed: int
    base_crit_chance: float
    base_crit_damage: float


class HeroTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    image_path: str | None
    race: RaceOut
    character_class: CharacterClassOut


class HeroStatsOut(BaseModel):
    hp: int
    attack: int
    defense: int
    speed: int
    crit_chance: float
    crit_damage: float


class UserHeroOut(BaseModel):
    id: int
    name: str
    level: int
    xp: int
    xp_to_next_level: int | None
    visual_stage: int
    hero_template: HeroTemplateOut
    stats: HeroStatsOut


class CreateHeroRequest(BaseModel):
    hero_template_id: int
    name: str = Field(min_length=2, max_length=20)

    @field_validator("name")
    @classmethod
    def strip_and_validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 2:
            raise ValueError("Name must be at least 2 characters")
        return stripped
