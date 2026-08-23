from pydantic import BaseModel

from app.schemas.item import ItemAffixOut, ItemStatsOut


class ChestRarityProbabilityOut(BaseModel):
    rarity: str
    probability: float


class ChestOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    price: int
    image_path: str | None
    guaranteed_min_rarity: str | None
    is_active: bool
    rarity_probabilities: list[ChestRarityProbabilityOut]


class ChestSummaryOut(BaseModel):
    id: int
    name: str


class ChestRewardOut(BaseModel):
    item_id: int
    item_template_id: int
    name: str
    slot: str
    tier: int
    rarity: str
    image_path: str | None
    stats: ItemStatsOut
    affixes: list[ItemAffixOut]


class ChestOpenResult(BaseModel):
    opening_id: int
    chest: ChestSummaryOut
    reward: ChestRewardOut
    balance: int


class OpenChestRequest(BaseModel):
    idempotency_key: str | None = None


class FreeChestStatusOut(BaseModel):
    chest: ChestOut
    is_available: bool
    next_available_at: str | None


class ChestOpeningHistoryOut(BaseModel):
    id: int
    chest: ChestSummaryOut
    reward_item_id: int
    reward_item_name: str
    reward_rarity: str
    price_paid: int
    created_at: str


# --- admin CRUD ---------------------------------------------------------

class ChestRarityProbabilityIn(BaseModel):
    rarity: str
    probability: float


class ChestCreate(BaseModel):
    slug: str
    name: str
    description: str = ""
    price: int
    image_path: str | None = None
    guaranteed_min_rarity: str | None = None
    is_active: bool = True
    sort_order: int = 0
    rarity_probabilities: list[ChestRarityProbabilityIn]


class ChestUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: int | None = None
    image_path: str | None = None
    guaranteed_min_rarity: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    rarity_probabilities: list[ChestRarityProbabilityIn] | None = None
