"""Pure-function tests for the skill budget/cost formulas — no DB involved."""

import pytest

from app.services.skill_progression import (
    MAX_SKILL_LEVEL,
    MIN_SKILL_LEVEL,
    SkillBudgetConfig,
    SkillUpgradeCostConfig,
    total_skill_budget,
    upgrade_cost,
)


def test_skill_level_bounds_are_1_to_10():
    assert MIN_SKILL_LEVEL == 1
    assert MAX_SKILL_LEVEL == 10


def test_default_budget_is_one_point_per_hero_level():
    assert total_skill_budget(1) == 1
    assert total_skill_budget(50) == 50
    assert total_skill_budget(100) == 100


def test_budget_config_is_swappable_for_balancing():
    generous = SkillBudgetConfig(points_per_hero_level=2.0)
    assert total_skill_budget(10, config=generous) == 20


def test_default_upgrade_cost_is_flat_one_point():
    assert upgrade_cost(0) == 1  # learning the skill for the first time
    assert upgrade_cost(5) == 1
    assert upgrade_cost(9) == 1


def test_upgrade_cost_config_can_scale_with_skill_level():
    steeper = SkillUpgradeCostConfig(base_cost=1.0, growth_per_skill_level=0.5)
    assert upgrade_cost(0, config=steeper) == 1
    assert upgrade_cost(4, config=steeper) == 3  # 1 + 0.5*4 = 3


@pytest.mark.parametrize("level", [1, 50, 100])
def test_budget_never_negative(level):
    assert total_skill_budget(level) >= 0
