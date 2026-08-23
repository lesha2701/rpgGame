"""Pure, stateless equipment power formulas — same shape as
services/progression.py and services/skill_progression.py: everything a
future balance pass needs to touch lives in this one file, never in the
models or in per-item data.

Design (Stage 4 requirement 5 — a higher tier must always beat a lower tier
regardless of rarity, e.g. "Common Tier 2 > Legendary Tier 1"):

    tier_power(T)      = base_power * growth_per_tier ** (T - 1)
    item_power(T, R)   = tier_power(T) * RARITY_POWER_MULTIPLIER[R]
    affix_power(T)     = tier_power(T) * AFFIX_POWER_FRACTION   (per affix)

For the invariant to hold even in the worst case — a max-rarity (Legendary)
item at tier T vs. a min-rarity (Common, 0 affixes) item at tier T+1 — the
tier growth has to outrun the rarity ceiling plus every affix a Legendary
item can carry:

    growth_per_tier > max(RARITY_POWER_MULTIPLIER) + max(RARITY_AFFIX_COUNT) * AFFIX_POWER_FRACTION

DEFAULT_TIER_POWER/DEFAULT_RARITY below satisfy this with margin (2.2 vs.
the required >1.9) — assert_tier_dominance_holds() checks it programmatically
so a future rebalance can't silently break the guarantee, and
test_item_progression.py checks it empirically across every tier."""

from dataclasses import dataclass

from app.models.enums import EquipmentSlot, ItemStatType, Rarity

MIN_TIER = 1
MAX_TIER = 10
LEVELS_PER_TIER = 10


@dataclass(frozen=True)
class TierPowerConfig:
    base_power: float = 10.0
    growth_per_tier: float = 2.2


DEFAULT_TIER_POWER = TierPowerConfig()

RARITY_POWER_MULTIPLIER: dict[Rarity, float] = {
    Rarity.common: 1.0,
    Rarity.rare: 1.2,
    Rarity.epic: 1.45,
    Rarity.legendary: 1.75,
}

RARITY_AFFIX_COUNT: dict[Rarity, int] = {
    Rarity.common: 0,
    Rarity.rare: 1,
    Rarity.epic: 2,
    Rarity.legendary: 3,
}

AFFIX_POWER_FRACTION = 0.05

# How a slot's primary power allocation splits across stats — weights per
# slot always sum to 1.0, so an item's full primary power always lands
# somewhere regardless of slot.
SLOT_STAT_WEIGHTS: dict[EquipmentSlot, dict[ItemStatType, float]] = {
    EquipmentSlot.weapon: {ItemStatType.attack: 1.0},
    EquipmentSlot.helmet: {ItemStatType.hp: 0.5, ItemStatType.defense: 0.5},
    EquipmentSlot.armor: {ItemStatType.hp: 0.4, ItemStatType.defense: 0.6},
    EquipmentSlot.boots: {ItemStatType.speed: 1.0},
    EquipmentSlot.gloves: {ItemStatType.attack: 0.5, ItemStatType.speed: 0.5},
    EquipmentSlot.ring: {ItemStatType.attack: 0.5, ItemStatType.speed: 0.5},
    EquipmentSlot.amulet: {ItemStatType.hp: 0.5, ItemStatType.defense: 0.5},
}


@dataclass(frozen=True)
class ItemStatBundle:
    hp: float = 0.0
    attack: float = 0.0
    defense: float = 0.0
    speed: float = 0.0

    def __add__(self, other: "ItemStatBundle") -> "ItemStatBundle":
        return ItemStatBundle(
            hp=self.hp + other.hp,
            attack=self.attack + other.attack,
            defense=self.defense + other.defense,
            speed=self.speed + other.speed,
        )

    def total(self) -> float:
        return self.hp + self.attack + self.defense + self.speed


def tier_power(tier: int, config: TierPowerConfig = DEFAULT_TIER_POWER) -> float:
    if not (MIN_TIER <= tier <= MAX_TIER):
        raise ValueError(f"tier must be between {MIN_TIER} and {MAX_TIER}, got {tier}")
    return config.base_power * (config.growth_per_tier ** (tier - 1))


def item_power(tier: int, rarity: Rarity, config: TierPowerConfig = DEFAULT_TIER_POWER) -> float:
    return tier_power(tier, config) * RARITY_POWER_MULTIPLIER[rarity]


def affix_power(tier: int, config: TierPowerConfig = DEFAULT_TIER_POWER) -> float:
    return tier_power(tier, config) * AFFIX_POWER_FRACTION


def required_level_for_tier(tier: int) -> int:
    """Tier N requires hero level (N-1)*10 + 1 — the same 10-level bands as
    visual stages (services/progression.equipment_tier_for_level), just the
    inverse direction: level -> tier there, tier -> minimum level here."""
    if not (MIN_TIER <= tier <= MAX_TIER):
        raise ValueError(f"tier must be between {MIN_TIER} and {MAX_TIER}, got {tier}")
    return (tier - 1) * LEVELS_PER_TIER + 1


def compute_item_stats(
    slot: EquipmentSlot, tier: int, rarity: Rarity, affix_stat_types: list[ItemStatType]
) -> ItemStatBundle:
    """Primary allocation (slot weights * item_power) plus one affix_power
    contribution per affix, added onto whichever stat that affix targets."""
    power = item_power(tier, rarity)
    values = {stat: power * weight for stat, weight in SLOT_STAT_WEIGHTS[slot].items()}

    a_power = affix_power(tier)
    for stat_type in affix_stat_types:
        values[stat_type] = values.get(stat_type, 0.0) + a_power

    return ItemStatBundle(
        hp=values.get(ItemStatType.hp, 0.0),
        attack=values.get(ItemStatType.attack, 0.0),
        defense=values.get(ItemStatType.defense, 0.0),
        speed=values.get(ItemStatType.speed, 0.0),
    )


def assert_tier_dominance_holds(config: TierPowerConfig = DEFAULT_TIER_POWER) -> None:
    """Raises AssertionError if the current tuning no longer guarantees
    "Common Tier N+1 > Legendary Tier N" (worst case: max rarity + max
    affix count at tier N, vs. min rarity + 0 affixes at tier N+1). Called
    by a test so a careless rebalance edit fails loudly instead of quietly
    breaking the game's core progression promise."""
    max_rarity_multiplier = max(RARITY_POWER_MULTIPLIER.values())
    max_affix_count = max(RARITY_AFFIX_COUNT.values())
    required_growth = max_rarity_multiplier + max_affix_count * AFFIX_POWER_FRACTION
    if config.growth_per_tier <= required_growth:
        raise AssertionError(
            f"growth_per_tier ({config.growth_per_tier}) must exceed "
            f"{required_growth} for the tier-dominance invariant to hold"
        )
