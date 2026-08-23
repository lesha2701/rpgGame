"""Stage 13 — interactive PvE Campaign combat (Variant C from the design
report). CampaignBattle is a stateful, row-locked, resumable session,
structurally parallel to arena_service.py's ArenaMatch handling but
single-player: the hero's action and the round's resolution happen in the
SAME request (there's no second human to wait on), so there's no
pending_action field and no AFK sweep — see CampaignBattle's docstring.

Every damage/skill/cooldown/buff/debuff/dot/stun rule still comes from
battle_engine.py's public building blocks (`CombatantState`,
`tick_start_of_turn`, `apply_action`) — nothing is reimplemented here. The
genuinely new things this module owns:

  - Enemy Intent: the enemy's action for the UPCOMING round is decided one
    round ahead (`_queue_enemy_intent`) and shown to the player before they
    act. Once queued, the ability itself never silently changes (Stage 13
    spec §7) — only whether it actually executes can change, exactly like
    the hero's own chosen action: `_resolve_round`'s per-actor loop is the
    same generic tick -> stun-check -> resolve shape arena_service already
    uses, so a stunned/dead enemy simply never reaches its own apply_action
    call, for free, with zero enemy-specific code.
  - Interrupt: an `is_interrupt`-flagged hero skill cancels the enemy's
    queued action even through stun_immune. This is pure local logic here
    (a boolean set during the hero's loop iteration, consulted during the
    enemy's) — no new CombatantState field, no change to battle_engine.py
    or arena_service.py (see the Stage 13 design report's reasoning).
  - Boss phases: checked once per round against the boss's current HP%,
    rescaling its (attack, defense) from its ORIGINAL base numbers (never
    compounding across phases) and swapping its behavior_pattern.
  - Defend: a third action_type ArenaActionRequest never needed (PvP has
    no "impose tempo vs. read-and-react" requirement; Campaign does —
    Stage 13 spec §4/§5). Applied BEFORE the round's speed-order loop
    (see `_apply_defend_if_chosen`) so it protects against the enemy's
    action this round regardless of who's faster — matching the spec's
    own canonical example ("Heavy Strike -> Defend"), which would break
    if Defend only took effect on the hero's own (possibly later) turn.
  - ItemEffect: a small, explicit trigger->handler resolution
    (`_apply_item_effects`) around the existing apply_action calls —
    never a scripting engine (Stage 13 spec §10). Hero-only (enemies
    don't equip items), snapshotted once at battle creation from the
    hero's currently-equipped gear, same "frozen at creation" discipline
    as hero_combat_stats/hero_battle_skills. `on_status_applied` is
    intentionally unhandled in V1 — recognized by the schema/enum for
    future authoring, but nothing seeded uses it (see the Stage 13
    report's deferred-features section).
  - Reward split: First Clear pays the enemy's full reward_xp/reward_coins;
    every Repeat Clear pays REPEAT_CLEAR_REWARD_FRACTION of it — that
    fraction lives here, as the one place it's read from (Stage 13 spec
    §13: don't scatter the number across services)."""

import random
from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import ConflictError, NotFoundError
from app.models.battle import Battle
from app.models.boss_phase import BossPhase
from app.models.campaign_battle import CampaignBattle
from app.models.campaign_node import CampaignNode
from app.models.enemy_ability import EnemyAbility
from app.models.enemy_resistance import EnemyResistance
from app.models.enemy_template import EnemyTemplate
from app.models.enums import BattleResult, CampaignBattleStatus, TransactionType
from app.models.item_effect import ItemEffect
from app.models.user import User
from app.models.user_campaign_node_clear import UserCampaignNodeClear
from app.models.user_hero import UserHero
from app.models.user_item import UserItem
from app.schemas.campaign import (
    CampaignBattleOut,
    CampaignEnemyIntentOut,
    CampaignEnemyStateOut,
    CampaignHeroStateOut,
    CampaignSkillOut,
)
from app.schemas.battle import BattleLogEntryOut
from app.services import campaign_service
from app.services.battle_engine import (
    MAX_ROUNDS,
    BattleSkill,
    CombatantState,
    CombatantStats,
    TurnLogEntry,
    apply_action,
    combatant_state_from_dict,
    compute_basic_damage,
    tick_start_of_turn,
)
from app.services.battle_service import hero_battle_skills, hero_combat_stats
from app.services.reward_service import grant_hero_reward

# Illustrative V1 balance, same status as arena_service.ARENA_WIN_REWARD_XP/
# COINS — not final tuning. The one and only place this fraction is
# defined (Stage 13 spec §13): every Repeat Clear reward computation reads
# THIS constant, nothing recomputes or hardcodes 0.3 elsewhere.
REPEAT_CLEAR_REWARD_FRACTION = 0.3

# Defend: +50% of the hero's current effective_defense. Illustrative V1
# balance, same status as the constants above.
DEFEND_DEFENSE_BONUS_FRACTION = 0.5
# 2, not 1: defense_buff_turns_remaining only ticks down on the HERO's own
# turn (tick_start_of_turn), which happens once during THIS round's order
# loop regardless of who acts first. Setting this to 1 would have the
# hero's own tick immediately zero the bonus out before the enemy's turn
# ever resolves (if the enemy acts second) — silently breaking the exact
# "Heavy Strike -> Defend" example the spec gives, since Defend must
# survive through the enemy's action THIS round no matter the speed
# order. 2 guarantees that; it fades on the hero's tick next round unless
# renewed (with a minor, harmless side effect: if the hero is slower than
# the enemy next round too, one extra round of partial residual
# protection applies before the tick catches up).
DEFEND_BONUS_TURNS = 2


async def _fetch_hero_item_effects(db: AsyncSession, hero_id: int) -> list[ItemEffect]:
    """Equipment-granted combat behavior — hero-only (enemies don't equip
    items). Snapshotted once at battle creation (see start_campaign_battle)
    and never re-read mid-fight, same "frozen at creation" discipline as
    hero_combat_stats/hero_battle_skills: re-gearing mid-fight has zero
    effect on an already-running CampaignBattle, exactly like Arena."""
    result = await db.execute(
        select(ItemEffect)
        .join(UserItem, UserItem.item_template_id == ItemEffect.item_template_id)
        .where(UserItem.equipped_hero_id == hero_id)
        .order_by(ItemEffect.sort_order)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Enemy-side setup: catalog fetch + BattleSkill conversion
# ---------------------------------------------------------------------------


async def _fetch_enemy_abilities(db: AsyncSession, enemy_template_id: int) -> list[EnemyAbility]:
    result = await db.execute(
        select(EnemyAbility)
        .where(EnemyAbility.enemy_template_id == enemy_template_id, EnemyAbility.is_active.is_(True))
        .order_by(EnemyAbility.sort_order)
    )
    return list(result.scalars().all())


async def _fetch_enemy_resistances(db: AsyncSession, enemy_template_id: int) -> list[EnemyResistance]:
    result = await db.execute(select(EnemyResistance).where(EnemyResistance.enemy_template_id == enemy_template_id))
    return list(result.scalars().all())


async def _fetch_boss_phases(db: AsyncSession, enemy_template_id: int) -> list[BossPhase]:
    result = await db.execute(
        select(BossPhase).where(BossPhase.enemy_template_id == enemy_template_id).order_by(BossPhase.phase_order)
    )
    return list(result.scalars().all())


def _rehydrate_combatant(data: dict) -> CombatantState:
    """combatant_state_from_dict, plus a defensive cooldowns-key fix:
    battle.state is a JSON column, and JSON object keys are always
    strings on the wire — confirmed live against Postgres — so a
    CombatantState reloaded from the DB (i.e. every request after the one
    that wrote it) comes back with `cooldowns` keyed by str even though
    apply_action always WRITES an int key. Without normalizing back to
    int here, every cooldown lookup in this module (`actor.cooldowns.get(
    skill.skill_definition_id, 0)`, an int) would silently miss and treat
    an on-cooldown skill as ready. arena_service.py has this same
    dict[int,int]-through-JSON shape and is NOT touched by this fix — it
    stays out of Stage 13's scope; see the Stage 13 report's discovered-
    bugs section."""
    state = combatant_state_from_dict(data)
    state.cooldowns = {int(k): v for k, v in state.cooldowns.items()}
    return state


def _ability_to_battle_skill(ability: EnemyAbility) -> BattleSkill:
    # skill_definition_id reuses the ability's own row id — CombatantState.
    # cooldowns is just a dict[int, int], and enemy abilities and hero
    # skills are never looked up in the same dict, so there's no
    # collision risk in reusing the same field for a different id space.
    return BattleSkill(
        skill_definition_id=ability.id,
        name=ability.name,
        skill_type=ability.skill_type.value,
        power=float(ability.power),
        cooldown_turns=ability.cooldown_turns,
        sort_order=ability.sort_order,
        buff_stat=ability.buff_stat,
        status_label=ability.status_label,
    )


# ---------------------------------------------------------------------------
# Enemy Intent
# ---------------------------------------------------------------------------


def _damage_preview(power: float, defender: CombatantState, attacker_crit_damage: float) -> tuple[int, int]:
    min_damage = compute_basic_damage(power, defender.effective_defense, False, attacker_crit_damage)
    max_damage = compute_basic_damage(power, defender.effective_defense, True, attacker_crit_damage)
    return min_damage, max_damage


def _queue_enemy_intent(enemy_state: dict, enemy_combatant: CombatantState, hero_combatant: CombatantState) -> dict:
    """Decides the enemy's action for the NEXT round, one round ahead of
    when it resolves — this is what `_build_out` shows the player as
    "Enemy Intent" before they choose their own action. Cycles through
    enemy_state["pattern"] (a list of EnemyAbility.code strings), falling
    back to Basic Attack for this round only if the next-in-line ability
    is on cooldown (same tolerance _pick_ready_skill/Arena already apply
    to the hero side) — the pattern index still advances past it, so the
    fight doesn't get stuck retrying the same ability every round."""
    pattern: list[str] = enemy_state.get("pattern") or []
    abilities_by_code: dict[str, BattleSkill] = {
        code: BattleSkill(**data) for code, data in enemy_state.get("abilities", {}).items()
    }
    pattern_index = enemy_state.get("pattern_index", 0)

    chosen_code: Optional[str] = None
    chosen_ability: Optional[BattleSkill] = None
    for _ in range(len(pattern)):
        code = pattern[pattern_index % len(pattern)]
        pattern_index += 1
        candidate = abilities_by_code.get(code)
        if candidate is not None and enemy_combatant.cooldowns.get(candidate.skill_definition_id, 0) <= 0:
            chosen_code, chosen_ability = code, candidate
            break
    enemy_state["pattern_index"] = pattern_index

    if chosen_ability is None:
        min_dmg, max_dmg = _damage_preview(enemy_combatant.effective_attack, hero_combatant, enemy_combatant.stats.crit_damage)
        return {
            "ability_code": None,
            "name": "Атака",
            "skill_type": "damage",
            "status_label": None,
            "min_damage": min_dmg,
            "max_damage": max_dmg,
        }

    if chosen_ability.skill_type == "damage":
        min_dmg, max_dmg = _damage_preview(chosen_ability.power, hero_combatant, enemy_combatant.stats.crit_damage)
    else:
        min_dmg = max_dmg = None

    return {
        "ability_code": chosen_code,
        "name": chosen_ability.name,
        "skill_type": chosen_ability.skill_type,
        "status_label": chosen_ability.status_label,
        "min_damage": min_dmg,
        "max_damage": max_dmg,
    }


# ---------------------------------------------------------------------------
# Boss phases
# ---------------------------------------------------------------------------


def _pick_phase(phases: list[dict], hp_pct: float) -> Optional[dict]:
    # phases sorted phase_order DESC — the first (highest phase_order,
    # lowest threshold) whose threshold is still >= current HP% is the
    # most-advanced phase the boss currently qualifies for.
    for phase in sorted(phases, key=lambda p: p["phase_order"], reverse=True):
        if phase["hp_threshold_pct"] >= hp_pct:
            return phase
    return None


def _rescale_enemy_stats(enemy_state: dict, enemy_combatant: CombatantState, phase: dict) -> None:
    base_attack, base_defense = enemy_state["base_attack"], enemy_state["base_defense"]
    enemy_combatant.stats = replace(
        enemy_combatant.stats,
        attack=round(base_attack * float(phase["attack_multiplier"])),
        defense=round(base_defense * float(phase["defense_multiplier"])),
    )


def _init_boss_phase(enemy_state: dict, enemy_combatant: CombatantState) -> None:
    phases: list[dict] = enemy_state.get("phases") or []
    if not phases:
        enemy_state["phase_order"] = None
        return
    initial = min(phases, key=lambda p: p["phase_order"])
    enemy_state["phase_order"] = initial["phase_order"]
    if initial.get("behavior_pattern"):
        enemy_state["pattern"] = initial["behavior_pattern"]
    _rescale_enemy_stats(enemy_state, enemy_combatant, initial)


def _apply_boss_phase_if_changed(
    enemy_state: dict, enemy_combatant: CombatantState, log: list[TurnLogEntry], turn: int
) -> None:
    phases: list[dict] = enemy_state.get("phases") or []
    if not phases:
        return
    hp_pct = (max(0, enemy_combatant.current_hp) / enemy_combatant.stats.hp) * 100
    active = _pick_phase(phases, hp_pct)
    if active is None or active["phase_order"] == enemy_state.get("phase_order"):
        return

    enemy_state["phase_order"] = active["phase_order"]
    if active.get("behavior_pattern"):
        enemy_state["pattern"] = active["behavior_pattern"]
        enemy_state["pattern_index"] = 0
    _rescale_enemy_stats(enemy_state, enemy_combatant, active)

    # A phase transition must be visibly noticeable (Stage 13 spec §9) —
    # always logged as its own combat event, even when transition_text is
    # empty, so the frontend can show a phase-change beat either way.
    log.append(
        TurnLogEntry(
            turn=turn,
            attacker="enemy",
            target="enemy",
            action_type="phase_transition",
            skill_id=None,
            damage=0,
            critical=False,
            target_hp_after=enemy_combatant.current_hp,
            status_effects=[{"type": "boss_phase", "phase_order": active["phase_order"], "text": active.get("transition_text")}],
        )
    )


# ---------------------------------------------------------------------------
# ItemEffect resolution — small explicit trigger/effect_type handler,
# never a scripting engine (Stage 13 spec §10). Hero-only: enemies don't
# equip items, so `hero_combatant` is always the effect owner and always
# where a self-targeted effect (shield_bonus_pct, lifesteal_pct, an
# on_defend/on_hit_taken apply_status) lands; on_crit/on_hit_dealt's
# apply_status targets the enemy instead.
# ---------------------------------------------------------------------------


def _boosted_skill_for_status_bonus(
    skill: Optional[BattleSkill], enemy_combatant: CombatantState, item_effects: list[dict]
) -> Optional[BattleSkill]:
    """damage_bonus_vs_status needs to modify the outgoing damage BEFORE
    apply_action computes it, which apply_action's contract doesn't
    expose a hook for — so this builds a boosted COPY of the chosen skill
    (dataclasses.replace, power scaled up) and that copy is what actually
    gets passed into apply_action instead of the original. Scoped to
    skill-type actions only in V1: a Basic Attack has no BattleSkill
    object to replace power on (apply_action reads actor.effective_attack
    directly for that path) — a documented V1 simplification, not a bug."""
    if skill is None or enemy_combatant.dot_turns_remaining <= 0 or enemy_combatant.dot_status_label is None:
        return skill
    bonus_pct = sum(
        float(e["magnitude"])
        for e in item_effects
        if e["effect_type"] == "damage_bonus_vs_status" and e["status_label"] == enemy_combatant.dot_status_label
    )
    if bonus_pct <= 0:
        return skill
    return replace(skill, power=skill.power * (1 + bonus_pct / 100))


def _apply_item_effects(
    item_effects: list[dict],
    trigger: str,
    hero_combatant: CombatantState,
    enemy_combatant: CombatantState,
    turn: int,
    log: list[TurnLogEntry],
    last_damage: int = 0,
) -> None:
    for effect in item_effects:
        if effect["trigger"] != trigger:
            continue
        if effect["effect_type"] == "apply_status":
            target = enemy_combatant if trigger in ("on_crit", "on_hit_dealt") else hero_combatant
            target_name = "enemy" if target is enemy_combatant else "hero"
            target.dot_damage = float(effect["magnitude"])
            target.dot_turns_remaining = effect["duration_turns"] or 1
            target.dot_status_label = effect["status_label"]
            log.append(
                TurnLogEntry(
                    turn=turn, attacker="hero", target=target_name, action_type="item_effect", skill_id=None,
                    damage=0, critical=False, target_hp_after=target.current_hp,
                    status_effects=[{"type": "item_status", "status_label": effect["status_label"]}],
                )
            )
        elif effect["effect_type"] == "lifesteal_pct" and last_damage > 0:
            heal = round(last_damage * float(effect["magnitude"]) / 100)
            hero_combatant.current_hp = min(hero_combatant.stats.hp, hero_combatant.current_hp + heal)
            log.append(
                TurnLogEntry(
                    turn=turn, attacker="hero", target="hero", action_type="item_effect", skill_id=None,
                    damage=-heal, critical=False, target_hp_after=hero_combatant.current_hp,
                    status_effects=[{"type": "lifesteal", "amount": heal}],
                )
            )
        elif effect["effect_type"] == "shield_bonus_pct":
            bonus = round(hero_combatant.stats.hp * float(effect["magnitude"]) / 100)
            hero_combatant.shield_remaining += bonus
            log.append(
                TurnLogEntry(
                    turn=turn, attacker="hero", target="hero", action_type="item_effect", skill_id=None,
                    damage=0, critical=False, target_hp_after=hero_combatant.current_hp,
                    status_effects=[{"type": "shield_bonus", "amount": bonus}],
                )
            )
        # damage_bonus_vs_status is resolved separately, before
        # apply_action — see _boosted_skill_for_status_bonus.


def _apply_defend_if_chosen(
    hero_combatant: CombatantState,
    enemy_combatant: CombatantState,
    defended: bool,
    item_effects: list[dict],
    turn: int,
    log: list[TurnLogEntry],
) -> None:
    """Applied BEFORE the round's speed-order loop, unconditionally (not
    tied to turn order) — see the module docstring's Defend section for
    why: it must protect against the enemy's action this round regardless
    of who's faster, matching the spec's own "Heavy Strike -> Defend"
    example. Still gated on the hero being alive and not stunned (a
    stunned hero can't even raise their guard) using the CURRENT state
    entering this round — cheaper than routing through the loop's own
    tick+stun-check just to gate one pre-loop effect."""
    if not defended or not hero_combatant.is_alive or hero_combatant.stunned:
        return
    bonus = round(hero_combatant.effective_defense * DEFEND_DEFENSE_BONUS_FRACTION)
    hero_combatant.defense_bonus += bonus
    hero_combatant.defense_buff_turns_remaining = DEFEND_BONUS_TURNS
    log.append(
        TurnLogEntry(
            turn=turn, attacker="hero", target="hero", action_type="defend", skill_id=None, damage=0,
            critical=False, target_hp_after=hero_combatant.current_hp,
            status_effects=[{"type": "defend", "amount": bonus}],
        )
    )
    _apply_item_effects(item_effects, "on_defend", hero_combatant, enemy_combatant, turn, log)


# ---------------------------------------------------------------------------
# Round resolution
# ---------------------------------------------------------------------------


def _resolve_round(battle: CampaignBattle, action_type: str, skill_id: Optional[int], now: datetime) -> bool:
    """Applies the hero's chosen action AND the already-queued enemy
    intent in speed order, reusing tick_start_of_turn/apply_action
    unchanged from battle_engine.py. Returns True if this call is what
    just finished the battle."""
    state = battle.state
    hero_state, enemy_state = state["hero"], state["enemy"]

    hero_combatant = _rehydrate_combatant(hero_state["combatant"])
    enemy_combatant = _rehydrate_combatant(enemy_state["combatant"])
    hero_skills = {s["skill_definition_id"]: BattleSkill(**s) for s in hero_state["skills"]}
    abilities_by_code = {code: BattleSkill(**data) for code, data in enemy_state.get("abilities", {}).items()}

    intent = enemy_state["queued_intent"]
    enemy_action = abilities_by_code.get(intent["ability_code"]) if intent["ability_code"] else None

    hero_item_effects: list[dict] = hero_state.get("item_effects", [])
    hero_defended = action_type == "defend"
    hero_action: Optional[BattleSkill] = None
    if action_type == "skill":
        hero_action = hero_skills.get(skill_id)
    hero_action = _boosted_skill_for_status_bonus(hero_action, enemy_combatant, hero_item_effects)

    new_log: list[TurnLogEntry] = []
    turn = state["turn"]
    rng = random.Random()

    _apply_defend_if_chosen(hero_combatant, enemy_combatant, hero_defended, hero_item_effects, turn, new_log)

    hero_first = hero_combatant.stats.speed >= enemy_combatant.stats.speed  # hero wins ties, same convention as PvE/Arena
    order = [
        (hero_combatant, "hero", hero_action, enemy_combatant, "enemy"),
        (enemy_combatant, "enemy", enemy_action, hero_combatant, "hero"),
    ]
    if not hero_first:
        order.reverse()

    interrupt_enemy_action = False
    for actor, actor_name, pending_skill, target, target_name in order:
        if not hero_combatant.is_alive or not enemy_combatant.is_alive:
            break
        turn += 1
        if not tick_start_of_turn(actor, actor_name, turn, new_log):
            continue  # died to their own DoT before acting

        if actor.stunned:
            actor.stunned = False
            new_log.append(
                TurnLogEntry(
                    turn=turn, attacker=actor_name, target=actor_name, action_type="stunned",
                    skill_id=None, damage=0, critical=False, target_hp_after=actor.current_hp, status_effects=[],
                )
            )
            continue

        if actor_name == "enemy" and interrupt_enemy_action:
            # The hero's action this round cancelled the enemy's queued
            # intent (Stage 13 spec §5/§7) — the enemy's turn still ticks
            # (cooldowns/DoT), it just does nothing this round.
            new_log.append(
                TurnLogEntry(
                    turn=turn, attacker=actor_name, target=actor_name, action_type="interrupted",
                    skill_id=None, damage=0, critical=False, target_hp_after=actor.current_hp, status_effects=[],
                )
            )
            continue

        if actor_name == "hero" and hero_defended:
            # The defend bonus (and any on_defend item effects) were
            # already applied before this loop started — Defend consumes
            # the hero's turn slot, dealing no damage.
            continue

        # Cooldown recheck against the authoritative post-tick state — same
        # discipline arena_service uses for the hero's chosen skill. An
        # enemy's queued ability is always still ready here: nothing
        # decrements an enemy cooldown except the enemy's own tick, which
        # just ran a few lines above.
        resolved_skill = None
        if pending_skill is not None and actor.cooldowns.get(pending_skill.skill_definition_id, 0) <= 0:
            resolved_skill = pending_skill

        if actor_name == "hero" and resolved_skill is not None and resolved_skill.is_interrupt:
            interrupt_enemy_action = True

        apply_action(actor, actor_name, resolved_skill, target, target_name, turn, rng, new_log)

        if new_log and new_log[-1].damage > 0:
            last_damage = new_log[-1].damage
            if actor_name == "hero":
                if new_log[-1].critical:
                    _apply_item_effects(hero_item_effects, "on_crit", hero_combatant, enemy_combatant, turn, new_log, last_damage)
                _apply_item_effects(hero_item_effects, "on_hit_dealt", hero_combatant, enemy_combatant, turn, new_log, last_damage)
            elif target_name == "hero":
                _apply_item_effects(hero_item_effects, "on_hit_taken", hero_combatant, enemy_combatant, turn, new_log, last_damage)

    state["turn"] = turn
    hero_state["combatant"] = asdict(hero_combatant)
    enemy_state["combatant"] = asdict(enemy_combatant)

    finished = not hero_combatant.is_alive or not enemy_combatant.is_alive
    if not finished:
        battle.current_round += 1
        finished = battle.current_round > MAX_ROUNDS

    if finished:
        _finish_in_memory(battle, hero_combatant, enemy_combatant, now)
    else:
        _apply_boss_phase_if_changed(enemy_state, enemy_combatant, new_log, turn)
        enemy_state["combatant"] = asdict(enemy_combatant)  # a phase change may have rescaled stats
        enemy_state["queued_intent"] = _queue_enemy_intent(enemy_state, enemy_combatant, hero_combatant)

    battle.log = battle.log + [asdict(entry) for entry in new_log]
    return finished


def _finish_in_memory(battle: CampaignBattle, hero_combatant: CombatantState, enemy_combatant: CombatantState, now: datetime) -> None:
    """Same win-determination formula as simulate_battle (PvE): a
    double-KO or a round-cap stalemate both fall back to remaining HP%,
    hero winning ties — not Arena's separate HP%-comparison helper, this
    is single-player so "hero"/"enemy" naming matches PvE, not player_a/b."""
    if not hero_combatant.is_alive and not enemy_combatant.is_alive:
        won = True
    elif not enemy_combatant.is_alive:
        won = True
    elif not hero_combatant.is_alive:
        won = False
    else:
        hero_pct = hero_combatant.current_hp / hero_combatant.stats.hp
        enemy_pct = enemy_combatant.current_hp / enemy_combatant.stats.hp
        won = hero_pct >= enemy_pct

    battle.status = CampaignBattleStatus.finished
    battle.finished_at = now
    battle.result = BattleResult.won if won else BattleResult.lost


async def _record_node_clear(db: AsyncSession, user_id: int, node_id: int, now: datetime) -> bool:
    """Returns True iff this is the FIRST time this user has cleared this
    node — the only signal the reward split needs (Stage 13 spec §13).
    No extra row lock: the caller already holds the CampaignBattle row
    locked for the entire request, and a hero can have at most one
    running CampaignBattle at a time (partial unique index), so no two
    concurrent requests can reach this function for the same user."""
    result = await db.execute(
        select(UserCampaignNodeClear).where(UserCampaignNodeClear.user_id == user_id, UserCampaignNodeClear.node_id == node_id)
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        db.add(UserCampaignNodeClear(user_id=user_id, node_id=node_id, first_cleared_at=now, last_cleared_at=now, clear_count=1))
        return True
    existing.clear_count += 1
    existing.last_cleared_at = now
    return False


async def _resolve_and_reward(
    db: AsyncSession, battle: CampaignBattle, hero: UserHero, user: User, action_type: str, skill_id: Optional[int], now: datetime
) -> None:
    finished = _resolve_round(battle, action_type, skill_id, now)
    if not finished:
        return

    if battle.result == BattleResult.won:
        is_first_clear = await _record_node_clear(db, user.id, battle.node_id, now)
        enemy = await db.get(EnemyTemplate, battle.enemy_template_id)
        fraction = 1.0 if is_first_clear else REPEAT_CLEAR_REWARD_FRACTION
        reward_xp = round(enemy.reward_xp * fraction)
        reward_coins = round(enemy.reward_coins * fraction)

        battle.is_first_clear = is_first_clear
        battle.reward_xp = reward_xp
        battle.reward_coins = reward_coins

        await grant_hero_reward(
            db, hero.id, user.id, reward_xp, reward_coins, TransactionType.campaign_reward,
            f"Победа над {enemy.name}", related_object_type="campaign_node", related_object_id=battle.node_id,
        )
    else:
        battle.reward_xp = 0
        battle.reward_coins = 0

    # One ordinary immutable Battle row, unchanged shape — Battle-based
    # quest conditions (battles_won) and any Battle-derived leaderboard
    # pick this up automatically, no special-casing for a campaign source.
    db.add(
        Battle(
            user_id=user.id,
            hero_id=hero.id,
            enemy_template_id=battle.enemy_template_id,
            result=battle.result,
            turns=battle.current_round,
            log=battle.log,
            reward_xp=battle.reward_xp,
            reward_coins=battle.reward_coins,
            idempotency_key=None,
            created_at=now,
        )
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def _has_running_battle(db: AsyncSession, hero_id: int) -> bool:
    result = await db.execute(
        select(CampaignBattle.id)
        .where(CampaignBattle.hero_id == hero_id, CampaignBattle.status == CampaignBattleStatus.running)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def start_campaign_battle(db: AsyncSession, user: User, hero: UserHero, node_id: int) -> CampaignBattleOut:
    if await _has_running_battle(db, hero.id):
        raise ConflictError("Your hero already has an active Campaign battle")

    node = await db.get(CampaignNode, node_id)
    if node is None or not node.is_active:
        raise NotFoundError("Node not found")
    if node.enemy_template_id is None:
        raise ConflictError("This node has no battle")

    if not await campaign_service.is_node_available(db, user.id, node):
        raise ConflictError("This node is not available yet")

    enemy = await db.get(EnemyTemplate, node.enemy_template_id)
    if enemy is None or not enemy.is_active:
        raise NotFoundError("Enemy not found")

    # Deliberately NO hero.level >= enemy.level gate (Stage 13 spec §1/§2):
    # level raises the hero's odds via stats/gear/skills, it never
    # hard-blocks an attempt — unlike PvE's start_battle, which does gate.
    hero_stats = await hero_combat_stats(db, hero)
    hero_skills = await hero_battle_skills(db, hero.id)
    hero_combatant = CombatantState(stats=hero_stats, current_hp=hero_stats.hp)
    hero_item_effects = await _fetch_hero_item_effects(db, hero.id)
    hero_item_effects_out = [
        {
            "trigger": e.trigger.value, "effect_type": e.effect_type.value, "status_label": e.status_label,
            "magnitude": float(e.magnitude), "duration_turns": e.duration_turns,
        }
        for e in hero_item_effects
    ]

    abilities = await _fetch_enemy_abilities(db, enemy.id)
    resistances = await _fetch_enemy_resistances(db, enemy.id)
    phases = await _fetch_boss_phases(db, enemy.id) if enemy.is_boss else []

    enemy_stats = CombatantStats(
        hp=enemy.hp, attack=enemy.attack, defense=enemy.defense, speed=enemy.speed,
        crit_chance=float(enemy.crit_chance), crit_damage=float(enemy.crit_damage),
        resistances={r.status_label: float(r.multiplier) for r in resistances},
        stun_immune=enemy.stun_immune,
    )
    enemy_combatant = CombatantState(stats=enemy_stats, current_hp=enemy_stats.hp)

    enemy_state = {
        "combatant": asdict(enemy_combatant),
        "abilities": {a.code: asdict(_ability_to_battle_skill(a)) for a in abilities},
        "pattern": list(enemy.behavior_pattern) if enemy.behavior_pattern else [],
        "pattern_index": 0,
        "phases": [
            {
                "phase_order": p.phase_order,
                "hp_threshold_pct": float(p.hp_threshold_pct),
                "behavior_pattern": p.behavior_pattern,
                "attack_multiplier": float(p.attack_multiplier),
                "defense_multiplier": float(p.defense_multiplier),
                "unlock_ability_code": p.unlock_ability_code,
                "transition_text": p.transition_text,
            }
            for p in phases
        ],
        "phase_order": None,
        "base_attack": enemy.attack,
        "base_defense": enemy.defense,
    }
    _init_boss_phase(enemy_state, enemy_combatant)
    enemy_state["combatant"] = asdict(enemy_combatant)
    enemy_state["queued_intent"] = _queue_enemy_intent(enemy_state, enemy_combatant, hero_combatant)

    creation_log: list[TurnLogEntry] = []
    _apply_item_effects(hero_item_effects_out, "passive", hero_combatant, enemy_combatant, 0, creation_log)

    battle = CampaignBattle(
        user_id=user.id,
        hero_id=hero.id,
        node_id=node.id,
        enemy_template_id=enemy.id,
        status=CampaignBattleStatus.running,
        current_round=1,
        state={
            "turn": 0,
            "hero": {
                "combatant": asdict(hero_combatant),
                "skills": [asdict(s) for s in hero_skills],
                "item_effects": hero_item_effects_out,
            },
            "enemy": enemy_state,
        },
        log=[asdict(entry) for entry in creation_log],
        created_at=datetime.now(timezone.utc),
    )
    db.add(battle)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("Your hero already has an active Campaign battle")

    return _build_out(battle, enemy)


async def _lock_battle_or_404(db: AsyncSession, campaign_battle_id: int) -> CampaignBattle:
    result = await db.execute(
        select(CampaignBattle).where(CampaignBattle.id == campaign_battle_id).with_for_update().execution_options(populate_existing=True)
    )
    battle = result.scalar_one_or_none()
    if battle is None:
        raise NotFoundError("Campaign battle not found")
    return battle


def _assert_owns(battle: CampaignBattle, user_id: int) -> None:
    if battle.user_id != user_id:
        raise NotFoundError("Campaign battle not found")


async def submit_campaign_action(
    db: AsyncSession, user: User, hero: UserHero, campaign_battle_id: int, round_number: int, action_type: str, skill_id: Optional[int]
) -> CampaignBattleOut:
    """Idempotent by construction, same shape as arena_service.submit_action:
    the client's `round_number` is the operation's natural key — a retry
    before resolution or after the round already resolved is detected and
    replayed rather than re-applied."""
    battle = await _lock_battle_or_404(db, campaign_battle_id)
    _assert_owns(battle, user.id)
    enemy = await db.get(EnemyTemplate, battle.enemy_template_id)
    now = datetime.now(timezone.utc)

    if battle.status == CampaignBattleStatus.finished:
        db.add(battle)
        await db.commit()
        return _build_out(battle, enemy)

    if round_number < battle.current_round:
        db.add(battle)
        await db.commit()
        return _build_out(battle, enemy)  # stale retry — already resolved, no mutation

    if round_number > battle.current_round:
        raise ConflictError("Action submitted for a round that hasn't started yet", details={"current_round": battle.current_round})

    if action_type == "skill":
        known_ids = {s["skill_definition_id"] for s in battle.state["hero"]["skills"]}
        if skill_id not in known_ids:
            raise ConflictError("Your hero does not know this skill")

    await _resolve_and_reward(db, battle, hero, user, action_type, skill_id, now)
    # battle.state is mutated in place (state["hero"]["combatant"] = ...,
    # not battle.state = ...) — SQLAlchemy's JSON type doesn't autodetect
    # nested in-place mutation, so without this the round's outcome would
    # silently never reach the DB (current_round/status/log ARE plain
    # attribute reassignments and don't need it — only state does). Same
    # pattern arena_service.py uses for ArenaMatch.state.
    flag_modified(battle, "state")

    db.add(battle)
    await db.commit()
    return _build_out(battle, enemy)


async def get_campaign_battle(db: AsyncSession, user: User, campaign_battle_id: int) -> CampaignBattleOut:
    battle = await db.get(CampaignBattle, campaign_battle_id)
    if battle is None:
        raise NotFoundError("Campaign battle not found")
    _assert_owns(battle, user.id)
    enemy = await db.get(EnemyTemplate, battle.enemy_template_id)
    return _build_out(battle, enemy)


def _cooldown_lookup(cooldowns: dict, skill_definition_id: int) -> int:
    # `cooldowns` is the raw dict straight off battle.state — its key type
    # depends on whether this battle was just constructed in-process
    # (asdict() -> int keys) or reloaded from the JSON column (Postgres
    # round-trip -> str keys, confirmed live; see _rehydrate_combatant's
    # docstring). Try both rather than assuming one.
    return cooldowns.get(skill_definition_id, cooldowns.get(str(skill_definition_id), 0))


def _build_out(battle: CampaignBattle, enemy: EnemyTemplate) -> CampaignBattleOut:
    hero_state, enemy_state = battle.state["hero"], battle.state["enemy"]
    hero_combatant = hero_state["combatant"]
    enemy_combatant = enemy_state["combatant"]

    skills_out = [
        CampaignSkillOut(
            skill_definition_id=s["skill_definition_id"],
            name=s["name"],
            skill_type=s["skill_type"],
            cooldown_turns=s["cooldown_turns"],
            cooldown_remaining=_cooldown_lookup(hero_combatant["cooldowns"], s["skill_definition_id"]),
            is_interrupt=s["is_interrupt"],
        )
        for s in hero_state["skills"]
    ]

    intent = enemy_state.get("queued_intent")
    intent_out = (
        CampaignEnemyIntentOut(
            ability_code=intent["ability_code"], name=intent["name"], skill_type=intent["skill_type"],
            status_label=intent["status_label"], min_damage=intent["min_damage"], max_damage=intent["max_damage"],
        )
        if intent and battle.status == CampaignBattleStatus.running
        else None
    )

    return CampaignBattleOut(
        id=battle.id,
        node_id=battle.node_id,
        status=battle.status.value,
        current_round=battle.current_round,
        hero=CampaignHeroStateOut(
            current_hp=max(0, hero_combatant["current_hp"]),
            max_hp=hero_combatant["stats"]["hp"],
            attack_bonus=hero_combatant["attack_bonus"],
            buff_turns_remaining=hero_combatant["buff_turns_remaining"],
            defense_bonus=hero_combatant["defense_bonus"],
            defense_buff_turns_remaining=hero_combatant["defense_buff_turns_remaining"],
            shield_remaining=hero_combatant["shield_remaining"],
            stunned=hero_combatant["stunned"],
            dot_turns_remaining=hero_combatant["dot_turns_remaining"],
            skills=skills_out,
        ),
        enemy=CampaignEnemyStateOut(
            enemy_template_id=enemy.id,
            name=enemy.name,
            image_path=enemy.image_path,
            level=enemy.level,
            is_boss=enemy.is_boss,
            current_hp=max(0, enemy_combatant["current_hp"]),
            max_hp=enemy_combatant["stats"]["hp"],
            shield_remaining=enemy_combatant["shield_remaining"],
            stunned=enemy_combatant["stunned"],
            dot_turns_remaining=enemy_combatant["dot_turns_remaining"],
            phase_order=enemy_state.get("phase_order"),
            intent=intent_out,
        ),
        log=[BattleLogEntryOut(**entry) for entry in battle.log],
        result=battle.result.value if battle.result else None,
        reward_xp=battle.reward_xp,
        reward_coins=battle.reward_coins,
        is_first_clear=battle.is_first_clear,
        created_at=battle.created_at.isoformat(),
        finished_at=battle.finished_at.isoformat() if battle.finished_at else None,
    )
