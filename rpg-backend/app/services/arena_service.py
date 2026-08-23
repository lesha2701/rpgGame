"""PvP Arena — two players, one hero each, turn-based, no background
worker. Structurally closest to expedition_service.py (a resource that
spans real time and resolves via timestamp comparisons, not a scheduler)
crossed with the football app's tactico_service.py's shape (two humans
each submitting one action per round; whichever submission is the SECOND
for that round resolves it immediately, in that same request; a lazy sweep
defaults an overdue side to a fallback action instead of a background job).
See ARCHITECTURE.md's Stage 9 section for the full comparison and the
points where this deliberately diverges from Tactico (idempotent replay on
a duplicate/stale action instead of a 409, one fixed round timeout instead
of two tiers).

Combat mechanics are NOT reimplemented here — every damage/skill/cooldown/
buff/dot/stun rule comes from battle_engine.py's public building blocks
(`CombatantState`, `tick_start_of_turn`, `apply_action`), the same ones
`simulate_battle` (PvE) is built from. The only thing genuinely new here is
persisting that state as JSON between two players' separate HTTP requests,
and resolving one player-chosen action at a time instead of an AI-chosen
one."""

import random
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import ConflictError, NotFoundError
from app.core.timeutil import ensure_aware
from app.models.arena_match import ArenaMatch
from app.models.enums import ArenaMatchStatus, TransactionType
from app.models.user import User
from app.models.user_hero import UserHero
from app.schemas.arena import ArenaMatchOut, ArenaParticipantOut
from app.schemas.battle import BattleLogEntryOut
from app.services.battle_engine import (
    MAX_ROUNDS,
    BattleSkill,
    TurnLogEntry,
    apply_action,
    combatant_state_from_dict,
    tick_start_of_turn,
)
from app.services.battle_service import hero_battle_skills, hero_combat_stats
from app.services.hero_service import get_active_hero, lock_hero_for_update
from app.services.reward_service import grant_hero_reward

# Illustrative V1 balance, not final tuning — same caveat as every seeded
# EnemyTemplate/ExpeditionTemplate/QuestDefinition reward. No admin-tunable
# row for these two numbers: Arena has no natural per-match "catalog" row
# the way Chest/Enemy/Expedition/Quest do (every match is an arbitrary pair
# of heroes, not a selection from a template), so these live as plain
# module constants — same shape as battle_engine.MAX_ROUNDS/
# BUFF_DURATION_TURNS, not a config table.
ARENA_WIN_REWARD_XP = 50
ARENA_WIN_REWARD_COINS = 30

# 15 minutes per round, confirmed. One fixed deadline (not Tactico's
# two-tier "shorter window once one side has committed") — simpler, and
# nothing in the brief asked for the extra tier.
ROUND_TIMEOUT = timedelta(minutes=15)

SIDES = ("player_a", "player_b")


def _other_side(side: str) -> str:
    return "player_b" if side == "player_a" else "player_a"


async def _snapshot_side(db: AsyncSession, hero: UserHero) -> dict:
    """Captured ONCE, at match creation, via the exact same functions PvE
    battle_service uses — never re-read for the rest of the match. This is
    what makes a mid-match equipment/level/skill change on the hero have
    zero effect on an already-running Arena match (see the docstring on
    ArenaMatch and the test suite's snapshot-invariance tests)."""
    stats = await hero_combat_stats(db, hero)
    skills = await hero_battle_skills(db, hero.id)
    return {
        "combatant": {
            "stats": asdict(stats),
            "current_hp": stats.hp,
            "attack_bonus": 0.0,
            "buff_turns_remaining": 0,
            "shield_remaining": 0.0,
            "stunned": False,
            "dot_damage": 0.0,
            "dot_turns_remaining": 0,
            "cooldowns": {},
        },
        "skills": [asdict(s) for s in skills],
        "pending_action": None,
    }


async def _has_running_match(db: AsyncSession, hero_id: int) -> bool:
    result = await db.execute(
        select(ArenaMatch.id)
        .where(
            or_(ArenaMatch.player_a_hero_id == hero_id, ArenaMatch.player_b_hero_id == hero_id),
            ArenaMatch.status == ArenaMatchStatus.running,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _lock_hero_pair(db: AsyncSession, hero_id_a: int, hero_id_b: int) -> tuple[UserHero, UserHero]:
    """Locks both participants' hero rows, in a consistent (sorted) order
    regardless of which one is "player_a" — same deadlock-avoidance shape
    as the football app's sorted (claimant, referrer) pre-lock in
    free_pack_service.claim_free_pack, extended from Stage 7's
    single-hero-lock pattern to two heroes locked together. This is the
    PRIMARY mechanism that makes "check neither hero already has a running
    match, then insert one" atomic against a second concurrent challenge
    naming either hero — the partial unique indexes on ArenaMatch are
    defense in depth behind this, not the other way around."""
    first_id, second_id = sorted([hero_id_a, hero_id_b])
    locked_first = await lock_hero_for_update(db, first_id)
    locked_second = await lock_hero_for_update(db, second_id)
    by_id = {locked_first.id: locked_first, locked_second.id: locked_second}
    return by_id[hero_id_a], by_id[hero_id_b]


async def create_match(db: AsyncSession, user: User, hero: UserHero, opponent_user_id: int) -> ArenaMatchOut:
    if opponent_user_id == user.id:
        raise ConflictError("You cannot challenge yourself")

    opponent = await db.get(User, opponent_user_id)
    if opponent is None:
        raise NotFoundError("Opponent not found")
    opponent_hero = await get_active_hero(db, opponent)
    if opponent_hero is None:
        raise NotFoundError("Opponent doesn't have a hero yet")

    hero_a, hero_b = await _lock_hero_pair(db, hero.id, opponent_hero.id)

    if await _has_running_match(db, hero_a.id):
        raise ConflictError("Your hero is already in an active Arena match")
    if await _has_running_match(db, hero_b.id):
        raise ConflictError("Opponent is already in an active Arena match")

    now = datetime.now(timezone.utc)
    match = ArenaMatch(
        player_a_user_id=user.id,
        player_a_hero_id=hero_a.id,
        player_b_user_id=opponent_user_id,
        player_b_hero_id=hero_b.id,
        status=ArenaMatchStatus.running,
        current_round=1,
        state={
            "turn": 0,
            "player_a": await _snapshot_side(db, hero_a),
            "player_b": await _snapshot_side(db, hero_b),
        },
        log=[],
        round_deadline_at=now + ROUND_TIMEOUT,
        created_at=now,
    )
    db.add(match)

    try:
        await db.commit()
    except IntegrityError:
        # The partial unique indexes catching a race the hero-row locks
        # above should already have prevented — belt and suspenders, not
        # the expected path.
        await db.rollback()
        raise ConflictError("One of the heroes is already in an active Arena match")

    return await _build_out(db, match)


async def _lock_match_or_404(db: AsyncSession, match_id: int) -> ArenaMatch:
    # No of= needed: ArenaMatch declares no relationships (see its
    # docstring) — nothing for FOR UPDATE to collide with via an outer join.
    result = await db.execute(
        select(ArenaMatch).where(ArenaMatch.id == match_id).with_for_update().execution_options(populate_existing=True)
    )
    match = result.scalar_one_or_none()
    if match is None:
        raise NotFoundError("Match not found")
    return match


def _side_for_user(match: ArenaMatch, user_id: int) -> str:
    if match.player_a_user_id == user_id:
        return "player_a"
    if match.player_b_user_id == user_id:
        return "player_b"
    raise NotFoundError("Match not found")


def _finish_match_in_memory(match: ArenaMatch, combatant_a, combatant_b, now: datetime) -> None:
    """One formula covers every termination reason (a side's HP hit 0, both
    hit 0 the same round, or the round cap was reached with both still
    alive) — remaining HP% decides it, player_a winning an exact tie. A
    dead combatant simply has 0%, so "someone died" and "round-cap
    stalemate" don't need separate branches here."""
    a_pct = max(0, combatant_a.current_hp) / combatant_a.stats.hp
    b_pct = max(0, combatant_b.current_hp) / combatant_b.stats.hp
    a_wins = a_pct >= b_pct

    match.status = ArenaMatchStatus.finished
    match.finished_at = now
    match.winner_user_id = match.player_a_user_id if a_wins else match.player_b_user_id
    match.reward_xp = ARENA_WIN_REWARD_XP
    match.reward_coins = ARENA_WIN_REWARD_COINS


def _resolve_round_if_ready(match: ArenaMatch, now: datetime) -> bool:
    """Applies both sides' pending actions (if both are present) in speed
    order, reusing tick_start_of_turn/apply_action unchanged from
    battle_engine.py — the same mechanics PvE uses, just fed a
    player-chosen action instead of an AI-chosen one. Returns True if this
    call is what just finished the match (the caller uses that to know
    whether to grant the reward — exactly once, from the one call site that
    actually flips the match to `finished`, never from a replay path)."""
    state = match.state
    a_state, b_state = state["player_a"], state["player_b"]
    if a_state["pending_action"] is None or b_state["pending_action"] is None:
        return False  # still waiting on someone

    combatant_a = combatant_state_from_dict(a_state["combatant"])
    combatant_b = combatant_state_from_dict(b_state["combatant"])
    skills_a = {s["skill_definition_id"]: BattleSkill(**s) for s in a_state["skills"]}
    skills_b = {s["skill_definition_id"]: BattleSkill(**s) for s in b_state["skills"]}

    new_log: list[TurnLogEntry] = []
    turn = state["turn"]
    rng = random.Random()

    a_first = combatant_a.stats.speed >= combatant_b.stats.speed  # player_a wins ties, same convention as PvE
    order = [
        (combatant_a, "player_a", a_state["pending_action"], skills_a, combatant_b, "player_b"),
        (combatant_b, "player_b", b_state["pending_action"], skills_b, combatant_a, "player_a"),
    ]
    if not a_first:
        order.reverse()

    for actor, actor_name, pending, actor_skills, target, target_name in order:
        if not combatant_a.is_alive or not combatant_b.is_alive:
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

        chosen_skill: Optional[BattleSkill] = None
        if pending["action_type"] == "skill":
            candidate = actor_skills.get(pending["skill_id"])
            # Cooldown is checked HERE, post-tick, against the authoritative
            # state — not at submission time (a client-side cooldown check
            # at submission would be checking a pre-tick value one round
            # stale, since the tick for THIS round only happens now). A
            # skill that wasn't actually ready by resolution time falls
            # back to Basic Attack, same tolerance PvE's AI already has
            # when nothing it wants is off cooldown.
            if candidate is not None and actor.cooldowns.get(candidate.skill_definition_id, 0) <= 0:
                chosen_skill = candidate
        apply_action(actor, actor_name, chosen_skill, target, target_name, turn, rng, new_log)

    state["turn"] = turn
    a_state["combatant"] = asdict(combatant_a)
    b_state["combatant"] = asdict(combatant_b)
    a_state["pending_action"] = None
    b_state["pending_action"] = None
    match.log = match.log + [asdict(entry) for entry in new_log]

    if not combatant_a.is_alive or not combatant_b.is_alive:
        _finish_match_in_memory(match, combatant_a, combatant_b, now)
        return True

    match.current_round += 1
    if match.current_round > MAX_ROUNDS:
        _finish_match_in_memory(match, combatant_a, combatant_b, now)
        return True

    match.round_deadline_at = now + ROUND_TIMEOUT
    return False


def _apply_sweep_if_overdue(match: ArenaMatch, now: datetime) -> bool:
    """Lazy, opportunistic — called from inside a request that already
    holds the row locked (GET or POST .../action), never a scheduled job.
    Same shape as the football app's tactico_service._auto_play_overdue_
    rounds, minus the background worker and minus its random-choice
    default (Basic Attack is deterministic, matching PvE AI's own
    fallback, not football's "random card" — this game has a well-defined
    "do nothing clever" action, football's card game doesn't)."""
    if match.status != ArenaMatchStatus.running:
        return False
    if now < ensure_aware(match.round_deadline_at):
        return False

    changed = False
    for side in SIDES:
        if match.state[side]["pending_action"] is None:
            match.state[side]["pending_action"] = {"action_type": "basic_attack", "skill_id": None}
            changed = True
    return changed


async def _resolve_and_reward_if_ready(db: AsyncSession, match: ArenaMatch, now: datetime) -> None:
    if not _resolve_round_if_ready(match, now):
        return
    winner_user_id = match.winner_user_id
    winner_hero_id = match.player_a_hero_id if winner_user_id == match.player_a_user_id else match.player_b_hero_id
    await grant_hero_reward(
        db,
        winner_hero_id,
        winner_user_id,
        match.reward_xp,
        match.reward_coins,
        TransactionType.arena_reward,
        "Победа в PvP",
        related_object_type="arena_match",
        related_object_id=match.id,
    )


async def _sweep_and_maybe_finish(db: AsyncSession, match: ArenaMatch, now: datetime) -> None:
    if _apply_sweep_if_overdue(match, now):
        flag_modified(match, "state")
        await _resolve_and_reward_if_ready(db, match, now)


async def submit_action(
    db: AsyncSession, user: User, match_id: int, round_number: int, action_type: str, skill_id: Optional[int]
) -> ArenaMatchOut:
    """Idempotent by construction. The client's `round_number` is what
    makes a retry-after-the-round-already-resolved case safely detectable:
    if it no longer matches match.current_round, this submission is stale
    and is replayed (current state returned, nothing re-applied) rather
    than being silently treated as an action for whatever round is current
    now. A retry that arrives BEFORE resolution (this side already has a
    pending_action for the current round) is caught the same way — no
    idempotency_key needed, exactly like expedition/quest claims: this
    operates on a row that already exists and already has an id, and the
    round number IS that operation's natural key."""
    match = await _lock_match_or_404(db, match_id)
    side = _side_for_user(match, user.id)
    now = datetime.now(timezone.utc)

    await _sweep_and_maybe_finish(db, match, now)

    if match.status == ArenaMatchStatus.finished:
        db.add(match)
        await db.commit()
        return await _build_out(db, match)

    if round_number < match.current_round:
        db.add(match)
        await db.commit()
        return await _build_out(db, match)  # stale retry — round already resolved, no mutation
    if round_number > match.current_round:
        raise ConflictError(
            "Action submitted for a round that hasn't started yet",
            details={"current_round": match.current_round},
        )

    side_state = match.state[side]
    if side_state["pending_action"] is not None:
        db.add(match)
        await db.commit()
        return await _build_out(db, match)  # duplicate submission before resolution — no mutation

    if action_type == "skill":
        known_ids = {s["skill_definition_id"] for s in side_state["skills"]}
        if skill_id not in known_ids:
            raise ConflictError("Your hero does not know this skill")
        side_state["pending_action"] = {"action_type": "skill", "skill_id": skill_id}
    else:
        side_state["pending_action"] = {"action_type": "basic_attack", "skill_id": None}
    flag_modified(match, "state")

    await _resolve_and_reward_if_ready(db, match, now)

    db.add(match)
    await db.commit()
    return await _build_out(db, match)


async def get_match(db: AsyncSession, user: User, match_id: int) -> ArenaMatchOut:
    match = await _lock_match_or_404(db, match_id)
    _side_for_user(match, user.id)
    now = datetime.now(timezone.utc)
    await _sweep_and_maybe_finish(db, match, now)
    db.add(match)
    await db.commit()
    return await _build_out(db, match)


async def list_matches(db: AsyncSession, user: User) -> list[ArenaMatchOut]:
    result = await db.execute(
        select(ArenaMatch.id)
        .where(or_(ArenaMatch.player_a_user_id == user.id, ArenaMatch.player_b_user_id == user.id))
        .order_by(ArenaMatch.id.desc())
    )
    match_ids = result.scalars().all()

    now = datetime.now(timezone.utc)
    out = []
    for match_id in match_ids:
        match = await _lock_match_or_404(db, match_id)
        await _sweep_and_maybe_finish(db, match, now)
        db.add(match)
        await db.commit()
        out.append(await _build_out(db, match))
    return out


async def _participant_out(db: AsyncSession, match: ArenaMatch, side: str) -> ArenaParticipantOut:
    user_id = getattr(match, f"{side}_user_id")
    hero_id = getattr(match, f"{side}_hero_id")
    hero = await db.get(UserHero, hero_id)
    side_state = match.state[side]
    return ArenaParticipantOut(
        user_id=user_id,
        hero_id=hero_id,
        hero_name=hero.hero_template.name,
        current_hp=max(0, side_state["combatant"]["current_hp"]),
        max_hp=side_state["combatant"]["stats"]["hp"],
        has_acted_this_round=side_state["pending_action"] is not None,
    )


async def _build_out(db: AsyncSession, match: ArenaMatch) -> ArenaMatchOut:
    # ensure_aware before isoformat(): a match built from an in-memory
    # mutation this same request just made carries an aware datetime, but
    # one re-fetched fresh from SQLite (tests) comes back naive — without
    # normalizing both to aware first, the SAME match's finished_at could
    # serialize with or without a "+00:00" suffix depending on which path
    # built the response, breaking byte-for-byte replay comparisons.
    return ArenaMatchOut(
        id=match.id,
        status=match.status.value,
        current_round=match.current_round,
        round_deadline_at=ensure_aware(match.round_deadline_at).isoformat(),
        player_a=await _participant_out(db, match, "player_a"),
        player_b=await _participant_out(db, match, "player_b"),
        log=[BattleLogEntryOut(**entry) for entry in match.log],
        winner_user_id=match.winner_user_id,
        reward_xp=match.reward_xp,
        reward_coins=match.reward_coins,
        created_at=ensure_aware(match.created_at).isoformat(),
        finished_at=ensure_aware(match.finished_at).isoformat() if match.finished_at else None,
    )
