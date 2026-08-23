"""Pure, stateless leveling/stat formulas. Nothing here talks to the DB or
persists a computed value — see UserHero's docstring for why."""

from dataclasses import dataclass

from app.models.character_class import CharacterClass

MAX_LEVEL = 100
MIN_LEVEL = 1
LEVELS_PER_TIER = 10


@dataclass(frozen=True)
class XpCurveConfig:
    """The only place the leveling curve's shape lives — balance the whole
    game by editing DEFAULT_XP_CURVE below (or passing a different instance
    through xp_to_next_level/apply_xp_gain, e.g. from tests or a future
    admin-editable config row) without touching any calling code."""

    base: float = 50.0
    exponent: float = 1.8


DEFAULT_XP_CURVE = XpCurveConfig()


@dataclass(frozen=True)
class HeroStats:
    hp: int
    attack: int
    defense: int
    speed: int
    crit_chance: float
    crit_damage: float


@dataclass(frozen=True)
class LevelUpResult:
    level: int
    xp: int
    levels_gained: int


def compute_stats(character_class: CharacterClass, level: int) -> HeroStats:
    """Base + flat per-level growth, levels above 1. Crit stats are flat
    from the class in V1 (equipment/skills move them from later stages).
    Automatic — there is no manual stat-point allocation anywhere in V1."""
    levels_gained = level - 1
    return HeroStats(
        hp=character_class.base_hp + round(float(character_class.hp_per_level) * levels_gained),
        attack=character_class.base_attack + round(float(character_class.attack_per_level) * levels_gained),
        defense=character_class.base_defense + round(float(character_class.defense_per_level) * levels_gained),
        speed=character_class.base_speed + round(float(character_class.speed_per_level) * levels_gained),
        crit_chance=float(character_class.base_crit_chance),
        crit_damage=float(character_class.base_crit_damage),
    )


def xp_to_next_level(level: int, curve: XpCurveConfig = DEFAULT_XP_CURVE) -> int | None:
    """XP required to advance from `level` to `level + 1`; None at the cap
    (level 100 is terminal in V1 — there is no level 101 to progress toward)."""
    if level >= MAX_LEVEL:
        return None
    return round(curve.base * level**curve.exponent)


def apply_xp_gain(level: int, xp: int, xp_gained: int, curve: XpCurveConfig = DEFAULT_XP_CURVE) -> LevelUpResult:
    """Adds xp_gained to a hero currently at (level, xp) — xp being progress
    toward the *next* level, not a lifetime total — and resolves however
    many level-ups it triggers in one go, carrying the remainder forward
    across every threshold crossed (no XP is discarded on level-up). Once
    level 100 is reached, further XP has nowhere to go and is dropped —
    there is no level 101 for it to count toward.

    Pure function: takes no DB session, returns the new (level, xp) without
    persisting anything — see hero_service.grant_xp for the persisting half."""
    if xp_gained < 0:
        raise ValueError("xp_gained must not be negative")
    if xp < 0:
        raise ValueError("xp must not be negative")
    if not (MIN_LEVEL <= level <= MAX_LEVEL):
        raise ValueError(f"level must be between {MIN_LEVEL} and {MAX_LEVEL}, got {level}")

    new_level = level
    remaining = xp + xp_gained
    levels_gained = 0

    while new_level < MAX_LEVEL:
        needed = xp_to_next_level(new_level, curve)
        assert needed is not None  # guaranteed: new_level < MAX_LEVEL
        if remaining < needed:
            break
        remaining -= needed
        new_level += 1
        levels_gained += 1

    if new_level >= MAX_LEVEL:
        new_level = MAX_LEVEL
        remaining = 0  # nothing left to track progress toward

    return LevelUpResult(level=new_level, xp=remaining, levels_gained=levels_gained)


def visual_stage_for_level(level: int) -> int:
    """Levels 1-10 -> stage 1, 11-20 -> stage 2, ..., 91-100 -> stage 10.
    Always derived from level, never persisted — see UserHero's docstring."""
    return min(((level - 1) // LEVELS_PER_TIER) + 1, MAX_LEVEL // LEVELS_PER_TIER)


def equipment_tier_for_level(level: int) -> int:
    """Same 10-level cadence as visual stages — kept as its own named
    function since equipment tiering (Stage 4) is a separate concern that
    just happens to share the boundary formula."""
    return visual_stage_for_level(level)
