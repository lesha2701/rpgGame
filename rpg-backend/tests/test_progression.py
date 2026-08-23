"""Pure-function tests — no DB involved. These are the ground truth for the
leveling engine; test_hero_leveling.py separately checks the DB-backed
service wraps this correctly (locking, persistence, API surface)."""

import pytest

from app.services.progression import (
    MAX_LEVEL,
    MIN_LEVEL,
    XpCurveConfig,
    apply_xp_gain,
    equipment_tier_for_level,
    visual_stage_for_level,
    xp_to_next_level,
)


# --- xp_to_next_level -------------------------------------------------

def test_xp_to_next_level_is_positive_for_every_level_below_cap():
    for level in range(MIN_LEVEL, MAX_LEVEL):
        needed = xp_to_next_level(level)
        assert needed is not None
        assert needed > 0


def test_xp_to_next_level_grows_with_level():
    assert xp_to_next_level(50) > xp_to_next_level(10)


def test_xp_to_next_level_is_none_at_the_cap():
    assert xp_to_next_level(MAX_LEVEL) is None


def test_xp_curve_is_swappable_for_balancing():
    """The whole point of pulling the curve into XpCurveConfig: a different
    instance changes the result with zero changes to calling code."""
    default_cost = xp_to_next_level(10)
    gentler = XpCurveConfig(base=10.0, exponent=1.0)
    assert xp_to_next_level(10, curve=gentler) != default_cost
    assert xp_to_next_level(10, curve=gentler) == 100  # 10 * 10^1.0


# --- apply_xp_gain: basic accumulation ---------------------------------

def test_small_gain_below_threshold_does_not_level_up():
    needed = xp_to_next_level(1)
    result = apply_xp_gain(level=1, xp=0, xp_gained=needed - 1)
    assert result.level == 1
    assert result.xp == needed - 1
    assert result.levels_gained == 0


def test_exact_threshold_levels_up_with_zero_remainder():
    needed = xp_to_next_level(1)
    result = apply_xp_gain(level=1, xp=0, xp_gained=needed)
    assert result.level == 2
    assert result.xp == 0
    assert result.levels_gained == 1


# --- XP overflow is carried forward, never discarded --------------------

def test_overflow_past_threshold_carries_to_next_level():
    needed = xp_to_next_level(1)
    result = apply_xp_gain(level=1, xp=0, xp_gained=needed + 30)
    assert result.level == 2
    assert result.xp == 30
    assert result.levels_gained == 1


def test_existing_progress_plus_gain_carries_correctly():
    needed = xp_to_next_level(5)
    result = apply_xp_gain(level=5, xp=needed - 10, xp_gained=25)
    assert result.level == 6
    assert result.xp == 15  # (needed - 10) + 25 - needed
    assert result.levels_gained == 1


def test_huge_gain_cascades_through_multiple_levels_carrying_remainder():
    # Enough XP to clear levels 1, 2, and 3 with a known remainder left for level 4.
    l1, l2, l3 = xp_to_next_level(1), xp_to_next_level(2), xp_to_next_level(3)
    assert l1 and l2 and l3
    total = l1 + l2 + l3 + 7
    result = apply_xp_gain(level=1, xp=0, xp_gained=total)
    assert result.level == 4
    assert result.xp == 7
    assert result.levels_gained == 3


# --- decade boundaries (visual stage / equipment tier) -------------------

@pytest.mark.parametrize(
    "level,expected_stage",
    [(1, 1), (10, 1), (11, 2), (20, 2), (21, 3), (90, 9), (91, 10), (100, 10)],
)
def test_visual_stage_boundaries(level, expected_stage):
    assert visual_stage_for_level(level) == expected_stage


def test_equipment_tier_matches_visual_stage_cadence():
    for level in (1, 10, 11, 55, 91, 100):
        assert equipment_tier_for_level(level) == visual_stage_for_level(level)


def test_leveling_up_across_a_decade_boundary_changes_visual_stage():
    needed = xp_to_next_level(10)
    assert needed is not None
    before = apply_xp_gain(level=10, xp=0, xp_gained=needed - 1)
    assert visual_stage_for_level(before.level) == 1

    after = apply_xp_gain(level=10, xp=0, xp_gained=needed)
    assert after.level == 11
    assert visual_stage_for_level(after.level) == 2


# --- level cap: 100 is a hard ceiling ------------------------------------

def test_reaching_exactly_level_100_stops_there():
    total = sum(xp_to_next_level(lvl) for lvl in range(1, MAX_LEVEL))  # type: ignore[misc]
    result = apply_xp_gain(level=1, xp=0, xp_gained=total)
    assert result.level == MAX_LEVEL
    assert result.xp == 0
    assert result.levels_gained == MAX_LEVEL - 1


def test_overshooting_past_level_100_is_capped_not_errored():
    total = sum(xp_to_next_level(lvl) for lvl in range(1, MAX_LEVEL))  # type: ignore[misc]
    result = apply_xp_gain(level=1, xp=0, xp_gained=total + 999_999)
    assert result.level == MAX_LEVEL
    assert result.xp == 0


def test_xp_granted_while_already_at_level_100_is_a_noop():
    result = apply_xp_gain(level=MAX_LEVEL, xp=0, xp_gained=500)
    assert result.level == MAX_LEVEL
    assert result.xp == 0
    assert result.levels_gained == 0


# --- invalid input is rejected, not silently clamped ---------------------

def test_negative_xp_gained_is_rejected():
    with pytest.raises(ValueError):
        apply_xp_gain(level=1, xp=0, xp_gained=-1)


def test_negative_existing_xp_is_rejected():
    with pytest.raises(ValueError):
        apply_xp_gain(level=1, xp=-5, xp_gained=10)


@pytest.mark.parametrize("bad_level", [0, -1, MAX_LEVEL + 1])
def test_out_of_range_starting_level_is_rejected(bad_level):
    with pytest.raises(ValueError):
        apply_xp_gain(level=bad_level, xp=0, xp_gained=10)


def test_zero_gain_is_a_true_noop():
    result = apply_xp_gain(level=7, xp=42, xp_gained=0)
    assert result.level == 7
    assert result.xp == 42
    assert result.levels_gained == 0
