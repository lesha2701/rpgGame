"""Pure unit tests for app/services/battle_engine.py — no DB, no client,
no async. Every scenario is built from deterministic stats (crit_chance=0
unless the test is specifically about crits) so outcomes are exact
arithmetic, not probabilistic."""

import random

from app.services.battle_engine import BattleSkill, CombatantStats, compute_basic_damage, simulate_battle


def _stats(**overrides) -> CombatantStats:
    base = dict(hp=1000, attack=10, defense=5, speed=10, crit_chance=0.0, crit_damage=1.5)
    base.update(overrides)
    return CombatantStats(**base)


def _skill(**overrides) -> BattleSkill:
    base = dict(skill_definition_id=1, name="Test Skill", skill_type="damage", power=20, cooldown_turns=3, sort_order=1)
    base.update(overrides)
    return BattleSkill(**base)


# --- basic attack / turn order / damage formula -------------------------------

def test_basic_attack_deals_attack_minus_defense_damage():
    hero = _stats(attack=20, defense=5, speed=10)
    enemy = _stats(attack=10, defense=5, speed=1)
    outcome = simulate_battle(hero, [], enemy, random.Random(0))

    first = outcome.log[0]
    assert first["attacker"] == "hero"
    assert first["action_type"] == "attack"
    assert first["damage"] == 15  # max(1, 20-5)
    assert first["critical"] is False
    assert first["target_hp_after"] == enemy.hp - 15


def test_turn_order_is_decided_by_speed_hero_wins_ties():
    faster_enemy = simulate_battle(_stats(speed=5), [], _stats(speed=20), random.Random(0))
    assert faster_enemy.log[0]["attacker"] == "enemy"

    tie = simulate_battle(_stats(speed=10), [], _stats(speed=10), random.Random(0))
    assert tie.log[0]["attacker"] == "hero"


def test_critical_hit_multiplies_damage():
    hero = _stats(attack=20, defense=5, crit_chance=1.0, crit_damage=2.0)
    enemy = _stats(defense=5, speed=1)
    outcome = simulate_battle(hero, [], enemy, random.Random(0))

    first = outcome.log[0]
    assert first["critical"] is True
    assert first["damage"] == 30  # round((20-5) * 2.0)


def test_damage_never_drops_below_one():
    hero = _stats(attack=1, defense=5, speed=10)
    enemy = _stats(attack=1, defense=1000, speed=1)
    outcome = simulate_battle(hero, [], enemy, random.Random(0))
    assert outcome.log[0]["damage"] == 1


def test_compute_basic_damage_matches_the_documented_formula():
    assert compute_basic_damage(attack=20, defense=5, is_critical=False, crit_damage=1.5) == 15
    # round(22.5) banker's-rounds to 22 (nearest even), not 23 - Python's
    # round() is round-half-to-even, not round-half-up.
    assert compute_basic_damage(attack=20, defense=5, is_critical=True, crit_damage=1.5) == 22
    assert compute_basic_damage(attack=1, defense=100, is_critical=False, crit_damage=1.5) == 1


# --- skills: damage, cooldown, shield, buff, dot, stun -------------------------

def test_skill_damage_uses_skill_power_not_attack_and_respects_cooldown():
    skill = _skill(skill_type="damage", power=30, cooldown_turns=2, sort_order=1)
    hero = _stats(attack=5, defense=0, hp=100000, speed=20)
    enemy = _stats(attack=1, defense=0, hp=100000, speed=1)
    outcome = simulate_battle(hero, [skill], enemy, random.Random(0))

    hero_actions = [e for e in outcome.log if e["attacker"] == "hero" and e["action_type"] in ("attack", "skill")]
    # turn 1: skill ready -> skill damage (30, defense 0). turn 2 (hero's next
    # turn): cooldown still up (2 -> 1) -> falls back to basic attack (5).
    # turn 3 (hero's 3rd turn): cooldown expired (1 -> 0) -> skill again (30).
    assert [a["action_type"] for a in hero_actions[:3]] == ["skill", "attack", "skill"]
    assert [a["damage"] for a in hero_actions[:3]] == [30, 5, 30]


def test_shield_skill_absorbs_incoming_damage():
    skill = _skill(skill_type="shield", power=20, cooldown_turns=10, sort_order=1)
    hero = _stats(defense=0, hp=1000, speed=20)
    enemy = _stats(attack=15, defense=0, hp=1000, speed=1)
    outcome = simulate_battle(hero, [skill], enemy, random.Random(0))

    cast = next(e for e in outcome.log if e["attacker"] == "hero" and e["action_type"] == "skill")
    assert cast["status_effects"] == [{"type": "shield", "amount": 20}]

    first_enemy_attack = next(e for e in outcome.log if e["attacker"] == "enemy")
    assert first_enemy_attack["damage"] == 0  # fully absorbed (15 < 20 shield)
    assert first_enemy_attack["target_hp_after"] == hero.hp


def test_buff_skill_boosts_attack_for_its_duration_then_expires():
    skill = _skill(skill_type="buff", power=10, cooldown_turns=10, sort_order=1)
    hero = _stats(attack=10, defense=0, hp=100000, speed=20)
    enemy = _stats(attack=0, defense=0, hp=100000, speed=1)
    outcome = simulate_battle(hero, [skill], enemy, random.Random(0))

    hero_attacks = [e for e in outcome.log if e["attacker"] == "hero" and e["action_type"] == "attack"]
    # hero's 1st turn casts the buff (not a plain attack). The next two
    # basic attacks (hero's 2nd/3rd turns) are boosted; the 4th has reverted.
    assert hero_attacks[0]["damage"] == 20  # 10 base + 10 buff
    assert hero_attacks[1]["damage"] == 20
    assert hero_attacks[2]["damage"] == 10  # buff expired


def test_dot_skill_ticks_damage_on_targets_own_turns_then_stops():
    # cooldown_turns is deliberately far longer than the battle has hero
    # turns (MAX_ROUNDS=30) so the skill is never recast mid-test, which
    # would apply a second DOT_DURATION_TURNS=3 batch of ticks.
    skill = _skill(skill_type="dot", power=9, cooldown_turns=100, sort_order=1)
    hero = _stats(defense=0, hp=100000, speed=20)
    enemy = _stats(attack=0, defense=0, hp=100000, speed=1)
    outcome = simulate_battle(hero, [skill], enemy, random.Random(0))

    ticks = [e for e in outcome.log if e["action_type"] == "dot_tick"]
    assert len(ticks) == 3  # DOT_DURATION_TURNS
    assert all(t["attacker"] == "enemy" and t["target"] == "enemy" and t["damage"] == 9 for t in ticks)


def test_stun_skill_skips_the_targets_next_turn():
    skill = _skill(skill_type="stun", power=1, cooldown_turns=10, sort_order=1)
    hero = _stats(defense=0, hp=100000, speed=20)
    enemy = _stats(attack=5, defense=0, hp=100000, speed=1)
    outcome = simulate_battle(hero, [skill], enemy, random.Random(0))

    enemy_turns = [e for e in outcome.log if e["attacker"] == "enemy"]
    assert enemy_turns[0]["action_type"] == "stunned"
    assert enemy_turns[0]["damage"] == 0
    assert enemy_turns[1]["action_type"] == "attack"  # stun only skips one turn


# --- win/loss resolution --------------------------------------------------------

def test_hero_dies_first_results_in_a_loss():
    hero = _stats(hp=1, defense=0, speed=1)
    enemy = _stats(attack=999, defense=0, hp=100000, speed=20)
    outcome = simulate_battle(hero, [], enemy, random.Random(0))
    assert outcome.won is False
    assert outcome.turns == 1


def test_enemy_dies_first_results_in_a_win():
    hero = _stats(attack=999, defense=0, hp=100000, speed=20)
    enemy = _stats(hp=1, defense=0, speed=1)
    outcome = simulate_battle(hero, [], enemy, random.Random(0))
    assert outcome.won is True
    assert outcome.turns == 1


def test_round_cap_stalemate_is_resolved_by_remaining_hp_percentage_hero_wins_ties():
    # Perfectly symmetric combatants: every round they deal and take
    # identical damage, so after MAX_ROUNDS neither dies and both end at
    # the exact same HP% -> tie -> hero wins by the documented convention.
    hero = _stats(hp=10000, attack=10, defense=5, speed=10)
    enemy = _stats(hp=10000, attack=10, defense=5, speed=10)
    outcome = simulate_battle(hero, [], enemy, random.Random(0))

    assert outcome.turns == 60  # 30 rounds * 2 actions, nobody dies early
    assert outcome.won is True
    hero_last = next(e for e in reversed(outcome.log) if e["target"] == "hero")
    enemy_last = next(e for e in reversed(outcome.log) if e["target"] == "enemy")
    assert hero_last["target_hp_after"] == enemy_last["target_hp_after"] == 10000 - 5 * 30


# --- determinism -----------------------------------------------------------------

def test_same_seed_and_inputs_reproduce_the_exact_same_battle_log():
    skill = _skill(skill_type="damage", power=15, cooldown_turns=2, sort_order=1)
    hero = _stats(attack=12, defense=4, crit_chance=0.5, speed=11)
    enemy = _stats(attack=9, defense=3, crit_chance=0.3, speed=9)

    outcome_a = simulate_battle(hero, [skill], enemy, random.Random(42))
    outcome_b = simulate_battle(hero, [skill], enemy, random.Random(42))

    assert outcome_a.log == outcome_b.log
    assert outcome_a.won == outcome_b.won
    assert outcome_a.turns == outcome_b.turns


def test_different_seeds_can_produce_different_logs():
    hero = _stats(attack=12, defense=4, crit_chance=0.5, speed=11)
    enemy = _stats(attack=9, defense=3, crit_chance=0.5, speed=9)

    outcome_a = simulate_battle(hero, [], enemy, random.Random(1))
    outcome_b = simulate_battle(hero, [], enemy, random.Random(2))

    assert outcome_a.log != outcome_b.log
