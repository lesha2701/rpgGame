"""Pure battle simulation — no DB, no FastAPI, no commits, no imports from
anywhere else in this package except dataclasses/stdlib. Input in,
BattleOutcome out; every random decision goes through the caller-supplied
random.Random, so the exact same inputs + the same seed always reproduce
the exact same battle_log (required for deterministic tests).

Shared by two callers with different needs (Stage 9): `simulate_battle`
resolves an entire PvE fight synchronously in one call, picking each
action automatically via `_pick_ready_skill`. `services/arena_service.py`
(PvP) instead needs to apply ONE externally-chosen action at a time,
persisting `CombatantState` between HTTP requests while two human players
each submit their own action per round. Rather than duplicating the
skill-effect/damage logic in a second module, this file exposes the
building blocks `simulate_battle` is itself built from — `CombatantState`,
`tick_start_of_turn`, and `apply_action` — as public API. `_apply_skill`/
`_apply_shield`/`_pick_ready_skill` stay private: they're implementation
details of `apply_action`, not something either caller needs directly.

Turn order is round-based, not a continuous ATB queue: each round, the
faster combatant (by Speed) acts once, then the other acts once (hero wins
ties). Speed decides *order only* — it never enters the damage formula
itself, only attack/defense/crit do.

Scope (Stage 6): PvE only, one hero vs one enemy, enemy always Basic
Attacks (no enemy skills — see EnemyTemplate's docstring). Of SkillType's
7 values, only damage/shield/buff/dot/stun are implemented; heal and debuff
are out of scope for Stage 6 (not in the brief's required list, and no
seeded skill uses either type — see ARCHITECTURE.md for the full
reasoning). A hero with a heal/debuff-type skill simply never selects it
(treated as always on cooldown by the turn-taking loop).

Stage 13 addendum: a handful of fields below (CombatantStats.resistances/
stun_immune, CombatantState.defense_bonus/defense_buff_turns_remaining,
BattleSkill.buff_stat/status_label/is_interrupt) exist ONLY for
campaign_battle_service.py's interactive PvE — every one of them defaults
to the value that reproduces this module's Stage 6/9 behavior exactly
(empty resistances, stun_immune=False, defense_bonus=0, buff_stat="attack"
matching the only value that ever existed before). Neither
simulate_battle (PvE) nor arena_service.py sets any of them to anything
else, so this is additive, not a behavior change — confirmed by the full
existing test suite passing unmodified after this addendum landed."""

import random
from dataclasses import asdict, dataclass, field

MAX_ROUNDS = 30
BUFF_DURATION_TURNS = 3
DOT_DURATION_TURNS = 3

IMPLEMENTED_SKILL_TYPES = frozenset({"damage", "shield", "buff", "debuff", "dot", "stun"})


@dataclass(frozen=True)
class CombatantStats:
    hp: int
    attack: int
    defense: int
    speed: int
    crit_chance: float
    crit_damage: float
    # Stage 13: per-status damage multipliers (e.g. {"burn": 1.5} = 50%
    # extra Burn damage taken) — keyed by the same status_label strings
    # BattleSkill.status_label uses. Only campaign enemies ever populate
    # this; heroes and every pre-Stage-13 caller leave it empty, which is
    # a no-op (see _apply_skill's dot branch).
    resistances: dict[str, float] = field(default_factory=dict)
    # Stage 13: lets a boss ignore vanilla Stun (still counterable via a
    # SkillDefinition.is_interrupt-flagged skill — see BattleSkill below).
    stun_immune: bool = False


@dataclass(frozen=True)
class BattleSkill:
    """Everything simulate_battle needs about one of the hero's learned
    skills — deliberately not the ORM CharacterSkill/SkillDefinition
    objects themselves, so this module stays free of any DB-layer import."""

    skill_definition_id: int
    name: str
    skill_type: str
    power: float  # already computed via skill_progression.power_at_level by the caller
    cooldown_turns: int
    sort_order: int
    # Stage 13: which stat a buff/debuff modifies. "attack" reproduces
    # every skill that existed before this field did (the only behavior
    # buff-type skills ever had).
    buff_stat: str = "attack"
    # Stage 13: tags a dot-type skill's flavor (bleed/burn/poison) so
    # CombatantStats.resistances and ItemEffect (damage_bonus_vs_status)
    # have something to key off. None for every pre-Stage-13 dot skill —
    # harmless, resistances.get(None, 1.0) is always the 1.0 no-op.
    status_label: str | None = None
    # Stage 13: lets a hero skill cancel a queued campaign-enemy intent
    # even through stun_immune (see campaign_battle_service.py). Unused by
    # PvE/Arena — neither ever inspects this field.
    is_interrupt: bool = False


@dataclass
class CombatantState:
    stats: CombatantStats
    current_hp: int
    attack_bonus: float = 0.0
    buff_turns_remaining: int = 0
    # Stage 13: defense's own bonus + independent expiry timer, mirroring
    # attack_bonus/buff_turns_remaining exactly (same "reset to 3, whole
    # bonus zeroes at 0" shape) — kept as a SEPARATE pair rather than
    # reusing the attack ones so a defense buff/debuff's duration can
    # never accidentally tick down (or zero out) an unrelated attack
    # modifier. Always 0 for PvE/Arena — nothing there ever targets
    # "defense" via buff_stat.
    defense_bonus: float = 0.0
    defense_buff_turns_remaining: int = 0
    shield_remaining: float = 0.0
    stunned: bool = False
    dot_damage: float = 0.0
    dot_turns_remaining: int = 0
    # Stage 13: which status_label the active dot came from (None for
    # every pre-Stage-13 dot skill, since status_label itself defaults to
    # None) — campaign_battle_service.py's ItemEffect resolution
    # (damage_bonus_vs_status) needs to know WHICH status is ticking on a
    # target, not just that one is. Single-slot, same as dot_damage/
    # dot_turns_remaining themselves: applying a second dot overwrites the
    # first rather than stacking, so this can't drift out of sync with them.
    dot_status_label: str | None = None
    cooldowns: dict[int, int] = field(default_factory=dict)

    @property
    def effective_attack(self) -> float:
        return self.stats.attack + self.attack_bonus

    @property
    def effective_defense(self) -> float:
        return self.stats.defense + self.defense_bonus

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0


def combatant_state_from_dict(data: dict) -> CombatantState:
    """The other half of `dataclasses.asdict(state)` — only used by
    arena_service.py to rebuild a CombatantState from the JSON it persisted
    between two players' HTTP requests. PvE's simulate_battle never
    serializes anything (it resolves an entire fight in one call, fully
    in-memory), so it never needs this."""
    stats = CombatantStats(**data["stats"])
    return CombatantState(stats=stats, **{k: v for k, v in data.items() if k != "stats"})


@dataclass(frozen=True)
class TurnLogEntry:
    turn: int
    attacker: str  # "hero" | "enemy" — whose action/effect this entry represents
    target: str  # "hero" | "enemy" — who is affected
    action_type: str  # "attack" | "skill" | "dot_tick" | "stunned"
    skill_id: int | None
    damage: int
    critical: bool
    target_hp_after: int
    status_effects: list[dict]


@dataclass(frozen=True)
class BattleOutcome:
    won: bool
    turns: int
    log: list[dict]


def compute_basic_damage(attack: float, defense: float, is_critical: bool, crit_damage: float) -> int:
    """The one damage formula, used identically for basic attacks and
    damage-type skills (skills just substitute skill power for attack).
    Speed is deliberately not a parameter here — it only ever affects turn
    order, never the number itself."""
    base = max(1.0, attack - defense)
    return int(round(base * crit_damage)) if is_critical else int(round(base))


def roll_is_critical(crit_chance: float, rng: random.Random) -> bool:
    return rng.random() < crit_chance


def _apply_shield(state: CombatantState, incoming_damage: int) -> int:
    if state.shield_remaining <= 0:
        return incoming_damage
    absorbed = min(state.shield_remaining, float(incoming_damage))
    state.shield_remaining -= absorbed
    return int(round(incoming_damage - absorbed))


def tick_start_of_turn(
    state: CombatantState, name: str, turn: int, log: list[TurnLogEntry]
) -> bool:
    """Cooldowns/buff timers/DoT all tick once per this combatant's own
    turn (not once per round) — an entity that's slower and acts less
    often ticks its own timers less often too, which is the intended,
    simplest-to-reason-about behavior for a round-based (not ATB) engine.
    Returns False if the DoT tick killed them (their turn is skipped)."""
    for skill_id in list(state.cooldowns):
        if state.cooldowns[skill_id] > 0:
            state.cooldowns[skill_id] -= 1

    if state.buff_turns_remaining > 0:
        state.buff_turns_remaining -= 1
        if state.buff_turns_remaining == 0:
            state.attack_bonus = 0.0

    if state.defense_buff_turns_remaining > 0:
        state.defense_buff_turns_remaining -= 1
        if state.defense_buff_turns_remaining == 0:
            state.defense_bonus = 0.0

    if state.dot_turns_remaining > 0:
        dot_damage = round(state.dot_damage)
        state.current_hp -= dot_damage
        state.dot_turns_remaining -= 1
        log.append(
            TurnLogEntry(
                turn=turn,
                attacker=name,
                target=name,
                action_type="dot_tick",
                skill_id=None,
                damage=dot_damage,
                critical=False,
                target_hp_after=max(0, state.current_hp),
                status_effects=[],
            )
        )
        if not state.is_alive:
            return False

    return True


def _apply_skill(
    skill: BattleSkill,
    caster: CombatantState,
    caster_name: str,
    target: CombatantState,
    target_name: str,
    turn: int,
    rng: random.Random,
    log: list[TurnLogEntry],
) -> None:
    if skill.skill_type == "damage":
        is_crit = roll_is_critical(caster.stats.crit_chance, rng)
        raw = compute_basic_damage(skill.power, target.effective_defense, is_crit, caster.stats.crit_damage)
        dmg = _apply_shield(target, raw)
        target.current_hp -= dmg
        log.append(
            TurnLogEntry(
                turn=turn, attacker=caster_name, target=target_name, action_type="skill",
                skill_id=skill.skill_definition_id, damage=dmg, critical=is_crit,
                target_hp_after=max(0, target.current_hp), status_effects=[],
            )
        )
    elif skill.skill_type == "shield":
        caster.shield_remaining += skill.power
        log.append(
            TurnLogEntry(
                turn=turn, attacker=caster_name, target=caster_name, action_type="skill",
                skill_id=skill.skill_definition_id, damage=0, critical=False,
                target_hp_after=caster.current_hp,
                status_effects=[{"type": "shield", "amount": round(skill.power)}],
            )
        )
    elif skill.skill_type == "buff":
        # buff_stat defaults to "attack" — every skill that existed before
        # this field did takes this branch, byte-for-byte unchanged.
        if skill.buff_stat == "defense":
            caster.defense_bonus += skill.power
            caster.defense_buff_turns_remaining = BUFF_DURATION_TURNS
        else:
            caster.attack_bonus += skill.power
            caster.buff_turns_remaining = BUFF_DURATION_TURNS
        log.append(
            TurnLogEntry(
                turn=turn, attacker=caster_name, target=caster_name, action_type="skill",
                skill_id=skill.skill_definition_id, damage=0, critical=False,
                target_hp_after=caster.current_hp,
                status_effects=[{
                    "type": "buff", "stat": skill.buff_stat, "amount": round(skill.power),
                    "duration": BUFF_DURATION_TURNS,
                }],
            )
        )
    elif skill.skill_type == "debuff":
        # Mirrors "buff" exactly, targeting the enemy with a negative
        # amount instead of the caster with a positive one — same single
        # shared bonus field + timer per stat, same "last write wins,
        # whole bonus zeroes at 0" shape.
        if skill.buff_stat == "defense":
            target.defense_bonus -= skill.power
            target.defense_buff_turns_remaining = BUFF_DURATION_TURNS
        else:
            target.attack_bonus -= skill.power
            target.buff_turns_remaining = BUFF_DURATION_TURNS
        log.append(
            TurnLogEntry(
                turn=turn, attacker=caster_name, target=target_name, action_type="skill",
                skill_id=skill.skill_definition_id, damage=0, critical=False,
                target_hp_after=target.current_hp,
                status_effects=[{
                    "type": "debuff", "stat": skill.buff_stat, "amount": round(skill.power),
                    "duration": BUFF_DURATION_TURNS,
                }],
            )
        )
    elif skill.skill_type == "dot":
        # Resistance (a per-status_label multiplier on the TARGET's own
        # stats — "vulnerable to Bleed" = >1.0, "resistant to Fire" <1.0)
        # is baked into dot_damage once, at application time, not
        # re-applied every tick — status_label=None (every pre-Stage-13
        # dot skill) always looks up the 1.0 no-op default.
        resistance = target.stats.resistances.get(skill.status_label, 1.0) if skill.status_label else 1.0
        target.dot_damage = skill.power * resistance
        target.dot_turns_remaining = DOT_DURATION_TURNS
        target.dot_status_label = skill.status_label
        log.append(
            TurnLogEntry(
                turn=turn, attacker=caster_name, target=target_name, action_type="skill",
                skill_id=skill.skill_definition_id, damage=0, critical=False,
                target_hp_after=target.current_hp,
                status_effects=[{
                    "type": "dot", "label": skill.status_label, "amount": round(target.dot_damage),
                    "duration": DOT_DURATION_TURNS,
                }],
            )
        )
    elif skill.skill_type == "stun":
        if target.stats.stun_immune:
            log.append(
                TurnLogEntry(
                    turn=turn, attacker=caster_name, target=target_name, action_type="skill",
                    skill_id=skill.skill_definition_id, damage=0, critical=False,
                    target_hp_after=target.current_hp,
                    status_effects=[{"type": "stun_resisted"}],
                )
            )
        else:
            target.stunned = True
            log.append(
                TurnLogEntry(
                    turn=turn, attacker=caster_name, target=target_name, action_type="skill",
                    skill_id=skill.skill_definition_id, damage=0, critical=False,
                    target_hp_after=target.current_hp,
                    status_effects=[{"type": "stun", "duration": 1}],
                )
            )
    else:  # pragma: no cover - guarded by _pick_ready_skill only ever offering implemented types
        raise ValueError(f"Unsupported skill_type in battle: {skill.skill_type}")


def _pick_ready_skill(skills: list[BattleSkill], cooldowns: dict[int, int]) -> BattleSkill | None:
    for skill in sorted(skills, key=lambda s: s.sort_order):
        if skill.skill_type not in IMPLEMENTED_SKILL_TYPES:
            continue  # heal/debuff (or any future type): never selectable in Stage 6's engine
        if cooldowns.get(skill.skill_definition_id, 0) <= 0:
            return skill
    return None


def apply_action(
    actor: CombatantState,
    actor_name: str,
    action: BattleSkill | None,
    target: CombatantState,
    target_name: str,
    turn: int,
    rng: random.Random,
    log: list[TurnLogEntry],
) -> None:
    """Applies exactly ONE already-chosen action — `action=None` means
    Basic Attack, a `BattleSkill` means use that skill. Does NOT pick the
    action itself (that's the caller's job: `_pick_ready_skill` for PvE's
    automatic AI below, a submitted player choice for PvP's arena_service)
    and does NOT handle stun/DoT-death (the caller must have already
    called `tick_start_of_turn` and checked `actor.stunned` first — see
    `_take_turn` for the PvE sequencing both callers replicate)."""
    if action is not None:
        # damage/dot/stun target the enemy; shield/buff target the caster.
        skill_target, skill_target_name = (
            (actor, actor_name) if action.skill_type in ("shield", "buff") else (target, target_name)
        )
        _apply_skill(action, actor, actor_name, skill_target, skill_target_name, turn, rng, log)
        actor.cooldowns[action.skill_definition_id] = action.cooldown_turns
        return

    is_crit = roll_is_critical(actor.stats.crit_chance, rng)
    raw = compute_basic_damage(actor.effective_attack, target.effective_defense, is_crit, actor.stats.crit_damage)
    dmg = _apply_shield(target, raw)
    target.current_hp -= dmg
    log.append(
        TurnLogEntry(
            turn=turn, attacker=actor_name, target=target_name, action_type="attack",
            skill_id=None, damage=dmg, critical=is_crit, target_hp_after=max(0, target.current_hp),
            status_effects=[],
        )
    )


def _take_turn(
    actor: CombatantState,
    actor_name: str,
    actor_skills: list[BattleSkill],
    target: CombatantState,
    target_name: str,
    turn: int,
    rng: random.Random,
    log: list[TurnLogEntry],
) -> None:
    if not tick_start_of_turn(actor, actor_name, turn, log):
        return  # died to their own DoT before acting

    if actor.stunned:
        actor.stunned = False
        log.append(
            TurnLogEntry(
                turn=turn, attacker=actor_name, target=actor_name, action_type="stunned",
                skill_id=None, damage=0, critical=False, target_hp_after=actor.current_hp, status_effects=[],
            )
        )
        return

    skill = _pick_ready_skill(actor_skills, actor.cooldowns) if actor_skills else None
    apply_action(actor, actor_name, skill, target, target_name, turn, rng, log)


def simulate_battle(
    hero_stats: CombatantStats,
    hero_skills: list[BattleSkill],
    enemy_stats: CombatantStats,
    rng: random.Random,
) -> BattleOutcome:
    hero = CombatantState(stats=hero_stats, current_hp=hero_stats.hp)
    enemy = CombatantState(stats=enemy_stats, current_hp=enemy_stats.hp)
    log: list[TurnLogEntry] = []
    turn = 0

    for _round in range(1, MAX_ROUNDS + 1):
        hero_first = hero_stats.speed >= enemy_stats.speed  # hero wins ties
        order = [
            (hero, "hero", hero_skills, enemy, "enemy"),
            (enemy, "enemy", [], hero, "hero"),
        ]
        if not hero_first:
            order.reverse()

        for actor, actor_name, actor_skills, target, target_name in order:
            if not hero.is_alive or not enemy.is_alive:
                break
            turn += 1
            _take_turn(actor, actor_name, actor_skills, target, target_name, turn, rng, log)

        if not hero.is_alive or not enemy.is_alive:
            break

    if not hero.is_alive and not enemy.is_alive:
        won = True  # double-KO: hero wins, consistent with the tie-break convention
    elif not enemy.is_alive:
        won = True
    elif not hero.is_alive:
        won = False
    else:
        hero_pct = hero.current_hp / hero.stats.hp
        enemy_pct = enemy.current_hp / enemy.stats.hp
        won = hero_pct >= enemy_pct  # round cap reached: higher remaining HP% wins, hero on ties

    return BattleOutcome(won=won, turns=turn, log=[asdict(entry) for entry in log])
