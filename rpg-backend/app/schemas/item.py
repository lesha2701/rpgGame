from pydantic import BaseModel, ConfigDict


class ItemStatsOut(BaseModel):
    hp: float
    attack: float
    defense: float
    speed: float


class ItemAffixOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stat_type: str


class ItemTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slot: str
    tier: int
    rarity: str
    name: str
    description: str | None
    image_path: str | None
    required_hero_level: int
    stats: ItemStatsOut
    affixes: list[ItemAffixOut]


class UserItemOut(BaseModel):
    id: int
    item_template: ItemTemplateOut
    is_equipped: bool
    equipped_hero_id: int | None


class EquippedItemsOut(BaseModel):
    weapon: UserItemOut | None = None
    helmet: UserItemOut | None = None
    armor: UserItemOut | None = None
    boots: UserItemOut | None = None
    gloves: UserItemOut | None = None
    ring: UserItemOut | None = None
    amulet: UserItemOut | None = None
