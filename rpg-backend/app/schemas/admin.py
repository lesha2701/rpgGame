"""Admin-only Out/Create/Update schemas for the catalog resources that only
had public, filtered (is_active=True), field-trimmed Out schemas before
(schemas/character.py, enemy.py, item.py, expedition.py, quest.py). Kept in
their own file rather than added to those — the public schemas intentionally
hide is_active/sort_order from players, and admin needs to see and edit both,
so these are deliberately separate types, not a modified public one."""

from pydantic import BaseModel, ConfigDict

from app.models.enums import EquipmentSlot, ItemStatType, QuestConditionType, Rarity


# --- Races -------------------------------------------------------------

class RaceAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    image_path: str | None
    is_active: bool
    sort_order: int


class RaceCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    image_path: str | None = None
    is_active: bool = True
    sort_order: int = 0


class RaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    image_path: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


# --- Character classes ---------------------------------------------------

class CharacterClassAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    image_path: str | None
    is_active: bool
    sort_order: int
    base_hp: int
    base_attack: int
    base_defense: int
    base_speed: int
    base_crit_chance: float
    base_crit_damage: float
    hp_per_level: float
    attack_per_level: float
    defense_per_level: float
    speed_per_level: float


class CharacterClassCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    image_path: str | None = None
    is_active: bool = True
    sort_order: int = 0
    base_hp: int
    base_attack: int
    base_defense: int
    base_speed: int
    base_crit_chance: float = 0.05
    base_crit_damage: float = 1.5
    hp_per_level: float
    attack_per_level: float
    defense_per_level: float
    speed_per_level: float


class CharacterClassUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    image_path: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    base_hp: int | None = None
    base_attack: int | None = None
    base_defense: int | None = None
    base_speed: int | None = None
    base_crit_chance: float | None = None
    base_crit_damage: float | None = None
    hp_per_level: float | None = None
    attack_per_level: float | None = None
    defense_per_level: float | None = None
    speed_per_level: float | None = None


# --- Hero templates --------------------------------------------------------

class HeroTemplateAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    race_id: int
    class_id: int
    name: str
    description: str | None
    image_path: str | None
    is_active: bool
    sort_order: int
    race: RaceAdminOut
    character_class: CharacterClassAdminOut


class HeroTemplateCreate(BaseModel):
    race_id: int
    class_id: int
    name: str
    description: str | None = None
    image_path: str | None = None
    is_active: bool = True
    sort_order: int = 0


class HeroTemplateUpdate(BaseModel):
    race_id: int | None = None
    class_id: int | None = None
    name: str | None = None
    description: str | None = None
    image_path: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


# --- Enemy templates ---------------------------------------------------

class EnemyTemplateAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    is_active: bool
    sort_order: int
    is_boss: bool
    stun_immune: bool
    behavior_pattern: list[str] | None


class EnemyTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    image_path: str | None = None
    level: int
    hp: int
    attack: int
    defense: int
    speed: int
    crit_chance: float = 0.05
    crit_damage: float = 1.5
    reward_xp: int
    reward_coins: int
    is_active: bool = True
    sort_order: int = 0
    is_boss: bool = False
    stun_immune: bool = False
    behavior_pattern: list[str] | None = None


class EnemyTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    image_path: str | None = None
    level: int | None = None
    hp: int | None = None
    attack: int | None = None
    defense: int | None = None
    speed: int | None = None
    crit_chance: float | None = None
    crit_damage: float | None = None
    reward_xp: int | None = None
    reward_coins: int | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    is_boss: bool | None = None
    stun_immune: bool | None = None
    behavior_pattern: list[str] | None = None


# --- Item templates ----------------------------------------------------

class ItemAffixAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stat_type: str


class ItemTemplateAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slot: str
    tier: int
    rarity: str
    name: str
    description: str | None
    image_path: str | None
    is_active: bool
    sort_order: int
    affixes: list[ItemAffixAdminOut]


class ItemTemplateCreate(BaseModel):
    slot: EquipmentSlot
    tier: int
    rarity: Rarity
    name: str
    description: str | None = None
    image_path: str | None = None
    is_active: bool = True
    sort_order: int = 0
    affix_stat_types: list[ItemStatType] = []


class ItemTemplateUpdate(BaseModel):
    # slot/tier/rarity are deliberately not editable here — item_progression
    # derives every UserItem's power from those three at read time, so
    # changing them post-creation would silently reprice every item already
    # granted from this template. Same immutability precedent as Chest.tier.
    name: str | None = None
    description: str | None = None
    image_path: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    affix_stat_types: list[ItemStatType] | None = None


# --- Expedition templates -----------------------------------------------

class ExpeditionTemplateAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    image_path: str | None
    duration_seconds: int
    required_hero_level: int
    reward_xp: int
    reward_coins: int
    is_active: bool
    sort_order: int


class ExpeditionTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    duration_seconds: int
    required_hero_level: int
    reward_xp: int
    reward_coins: int
    is_active: bool = True
    sort_order: int = 0


class ExpeditionTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    duration_seconds: int | None = None
    required_hero_level: int | None = None
    reward_xp: int | None = None
    reward_coins: int | None = None
    is_active: bool | None = None
    sort_order: int | None = None


# --- Quest definitions ---------------------------------------------------

class QuestDefinitionAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    condition_type: str
    target_value: int
    reward_xp: int
    reward_coins: int
    is_active: bool
    sort_order: int


class QuestDefinitionCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    condition_type: QuestConditionType
    target_value: int
    reward_xp: int
    reward_coins: int
    is_active: bool = True
    sort_order: int = 0


class QuestDefinitionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    condition_type: QuestConditionType | None = None
    target_value: int | None = None
    reward_xp: int | None = None
    reward_coins: int | None = None
    is_active: bool | None = None
    sort_order: int | None = None
