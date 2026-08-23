"""Pure-function tests for equipment power formulas — no DB involved.
test_default_config_satisfies_tier_dominance_for_every_tier below is the
main event: Stage 4's core balance rule, "a higher tier item is always
stronger than a lower tier item regardless of rarity" (e.g. Common Tier 2
beats Legendary Tier 1), checked exhaustively across the entire 1-10 range,
including the worst case where affixes are also stacked on the lower item."""

import pytest

from app.models.enums import EquipmentSlot, ItemStatType, Rarity
from app.services.item_progression import (
    MAX_TIER,
    MIN_TIER,
    RARITY_AFFIX_COUNT,
    RARITY_POWER_MULTIPLIER,
    TierPowerConfig,
    affix_power,
    assert_tier_dominance_holds,
    compute_item_stats,
    item_power,
    required_level_for_tier,
    tier_power,
)


def test_tier_power_grows_with_tier():
    assert tier_power(2) > tier_power(1)
    assert tier_power(10) > tier_power(9)


def test_tier_power_rejects_out_of_range_tier():
    with pytest.raises(ValueError):
        tier_power(0)
    with pytest.raises(ValueError):
        tier_power(11)


def test_rarity_multiplier_increases_power_within_a_tier():
    for tier in (1, 5, 10):
        assert item_power(tier, Rarity.common) < item_power(tier, Rarity.rare)
        assert item_power(tier, Rarity.rare) < item_power(tier, Rarity.epic)
        assert item_power(tier, Rarity.epic) < item_power(tier, Rarity.legendary)


def test_required_level_for_tier_matches_the_10_level_bands():
    assert required_level_for_tier(1) == 1
    assert required_level_for_tier(2) == 11
    assert required_level_for_tier(10) == 91


def test_default_config_satisfies_tier_dominance_invariant():
    """Guards the config itself — a careless future edit to growth_per_tier
    or the rarity multipliers that breaks the promise fails here loudly,
    before it could ever produce a bad in-game item."""
    assert_tier_dominance_holds()


def test_a_worse_config_would_violate_the_invariant():
    """Proves the assertion helper actually checks something (not a tautology)."""
    weak_growth = TierPowerConfig(base_power=10.0, growth_per_tier=1.5)
    with pytest.raises(AssertionError):
        assert_tier_dominance_holds(weak_growth)


@pytest.mark.parametrize("tier", range(MIN_TIER, MAX_TIER))
def test_common_next_tier_beats_legendary_this_tier_primary_power_only(tier):
    """The example given in the brief: Common Tier N+1 > Legendary Tier N."""
    legendary_this_tier = item_power(tier, Rarity.legendary)
    common_next_tier = item_power(tier + 1, Rarity.common)
    assert common_next_tier > legendary_this_tier


@pytest.mark.parametrize("tier", range(MIN_TIER, MAX_TIER))
def test_common_next_tier_beats_legendary_this_tier_even_with_max_affixes(tier):
    """Worst case for the invariant: the lower-tier item is Legendary with
    every affix it can have; the higher-tier item is Common with none."""
    legendary_total = item_power(tier, Rarity.legendary) + RARITY_AFFIX_COUNT[Rarity.legendary] * affix_power(tier)
    common_next_tier_total = item_power(tier + 1, Rarity.common)  # 0 affixes
    assert common_next_tier_total > legendary_total


@pytest.mark.parametrize("tier", range(MIN_TIER, MAX_TIER))
def test_tier_dominance_via_full_stat_computation(tier):
    """Same invariant, but through compute_item_stats (what the API
    actually returns) rather than the raw item_power formula — catches a
    bug in the slot-weight distribution that the formula-level tests above
    wouldn't (weights always sum to 1.0, so total() should equal item_power
    + affix contributions regardless of how it's split across stats)."""
    max_affixes = [ItemStatType.hp] * RARITY_AFFIX_COUNT[Rarity.legendary]
    lower = compute_item_stats(EquipmentSlot.armor, tier, Rarity.legendary, max_affixes)
    higher = compute_item_stats(EquipmentSlot.armor, tier + 1, Rarity.common, [])
    assert higher.total() > lower.total()


def test_affix_power_scales_with_tier():
    assert affix_power(5) > affix_power(1)


def test_rarity_affix_counts_are_0_1_2_3():
    assert RARITY_AFFIX_COUNT[Rarity.common] == 0
    assert RARITY_AFFIX_COUNT[Rarity.rare] == 1
    assert RARITY_AFFIX_COUNT[Rarity.epic] == 2
    assert RARITY_AFFIX_COUNT[Rarity.legendary] == 3


def test_compute_item_stats_primary_allocation_sums_to_item_power_before_affixes():
    stats = compute_item_stats(EquipmentSlot.weapon, 3, Rarity.common, [])
    assert stats.total() == pytest.approx(item_power(3, Rarity.common))


def test_compute_item_stats_adds_one_affix_power_per_affix():
    no_affix = compute_item_stats(EquipmentSlot.ring, 4, Rarity.epic, [])
    with_affixes = compute_item_stats(EquipmentSlot.ring, 4, Rarity.epic, [ItemStatType.hp, ItemStatType.speed])
    assert with_affixes.total() == pytest.approx(no_affix.total() + 2 * affix_power(4))


def test_slot_weights_cover_all_four_stat_types_across_slots():
    """Sanity check on the seed/design data, not the formula: every stat
    type should be reachable from at least one slot, or that stat could
    never appear on any item."""
    from app.services.item_progression import SLOT_STAT_WEIGHTS

    covered = set()
    for weights in SLOT_STAT_WEIGHTS.values():
        covered.update(weights.keys())
    assert covered == {ItemStatType.hp, ItemStatType.attack, ItemStatType.defense, ItemStatType.speed}


def test_rarity_power_multiplier_keys_cover_every_rarity():
    assert set(RARITY_POWER_MULTIPLIER.keys()) == set(Rarity)
