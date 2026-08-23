"""Pure, stateless skill-budget/cost formulas — same shape as
services/progression.py's XpCurveConfig.

Design note (Stage 3 requirement: "don't create a separate skill_points
resource unless the implementation actually needs one"): rather than adding
a stored currency, a hero's skill-point budget is *computed* from their
existing level (total_skill_budget) and compared against the sum of levels
already spent across their learned CharacterSkill rows. Nothing new is
persisted — "insufficient resources" is a genuine, enforceable condition
derived entirely from state that already exists (hero.level + owned skill
levels), and the two formulas below are the one place to rebalance it."""

from dataclasses import dataclass
from math import floor

from app.models.skill_definition import SkillDefinition

MIN_SKILL_LEVEL = 1
MAX_SKILL_LEVEL = 10


@dataclass(frozen=True)
class SkillBudgetConfig:
    points_per_hero_level: float = 1.0


DEFAULT_SKILL_BUDGET = SkillBudgetConfig()


@dataclass(frozen=True)
class SkillUpgradeCostConfig:
    base_cost: float = 1.0
    growth_per_skill_level: float = 0.0


DEFAULT_SKILL_UPGRADE_COST = SkillUpgradeCostConfig()


def total_skill_budget(hero_level: int, config: SkillBudgetConfig = DEFAULT_SKILL_BUDGET) -> int:
    """Total skill-level points a hero has earned from leveling, to date."""
    return floor(hero_level * config.points_per_hero_level)


def upgrade_cost(current_skill_level: int, config: SkillUpgradeCostConfig = DEFAULT_SKILL_UPGRADE_COST) -> int:
    """Cost, in skill-budget points, to raise a skill from
    current_skill_level to current_skill_level + 1. current_skill_level=0
    means "not yet learned" — this is the cost to learn it at level 1."""
    return round(config.base_cost + config.growth_per_skill_level * current_skill_level)


def power_at_level(skill: SkillDefinition, skill_level: int) -> float:
    """Effect magnitude at a given skill level — future battle-engine input,
    not applied to anything yet."""
    return float(skill.base_power) + float(skill.power_per_skill_level) * (skill_level - 1)
