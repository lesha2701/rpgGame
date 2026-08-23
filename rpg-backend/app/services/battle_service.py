"""DB-aware orchestration around the pure app/services/battle_engine.py.
Structurally mirrors chest_service.open_chest: early idempotency lookup,
validate, lock the rows that need mutating, mutate, commit once, with a
commit-time IntegrityError fallback for a genuine concurrent retry race —
see that module (and ARCHITECTURE.md's Stage 5 section) for where this
pattern was first proven against real Postgres.

The one thing this module owns that chest_service didn't need: folding
reward_service.grant_hero_reward (XP + coins) into the SAME transaction as
the Battle insert — grant_hero_reward doesn't commit on its own (see that
module's docstring), so nothing lands unless the Battle row does too."""

import random
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.battle import Battle
from app.models.enemy_template import EnemyTemplate
from app.models.enums import BattleResult, TransactionType
from app.models.user import User
from app.models.user_hero import UserHero
from app.schemas.battle import BattleLogEntryOut, BattleOut, EnemySummaryOut
from app.schemas.enemy import EnemyOut
from app.services.battle_engine import BattleSkill, CombatantStats, simulate_battle
from app.services.hero_service import hero_progress_out, hero_to_out
from app.services.reward_service import grant_hero_reward
from app.services.skill_progression import power_at_level
from app.services.skill_service import get_hero_skills


async def _get_enemy_or_404(db: AsyncSession, enemy_template_id: int) -> EnemyTemplate:
    enemy = await db.get(EnemyTemplate, enemy_template_id)
    if enemy is None:
        raise NotFoundError("Enemy not found")
    return enemy


def _assert_enemy_available(enemy: EnemyTemplate) -> None:
    if not enemy.is_active:
        raise ConflictError("This enemy is not currently available")


async def list_enemies(db: AsyncSession) -> list[EnemyTemplate]:
    result = await db.execute(
        select(EnemyTemplate).where(EnemyTemplate.is_active.is_(True)).order_by(EnemyTemplate.level, EnemyTemplate.sort_order)
    )
    return list(result.scalars().all())


def enemy_to_out(enemy: EnemyTemplate, hero_level: int | None) -> EnemyOut:
    return EnemyOut(
        id=enemy.id,
        name=enemy.name,
        description=enemy.description,
        image_path=enemy.image_path,
        level=enemy.level,
        hp=enemy.hp,
        attack=enemy.attack,
        defense=enemy.defense,
        speed=enemy.speed,
        crit_chance=float(enemy.crit_chance),
        crit_damage=float(enemy.crit_damage),
        reward_xp=enemy.reward_xp,
        reward_coins=enemy.reward_coins,
        is_available_to_user=(hero_level is not None and hero_level >= enemy.level),
    )


async def hero_combat_stats(db: AsyncSession, hero: UserHero) -> CombatantStats:
    """Reuses hero_to_out (the exact function /heroes/me already calls) so
    battle math can never drift from what the player sees as their stats —
    not a second, parallel stats computation. Public: arena_service.py
    (Stage 9) reuses this and hero_battle_skills below to build its
    match-start snapshot — see that module for why the snapshot is taken
    once and never re-read for the rest of an Arena match."""
    hero_out = await hero_to_out(db, hero)
    return CombatantStats(
        hp=hero_out.stats.hp,
        attack=hero_out.stats.attack,
        defense=hero_out.stats.defense,
        speed=hero_out.stats.speed,
        crit_chance=hero_out.stats.crit_chance,
        crit_damage=hero_out.stats.crit_damage,
    )


async def hero_battle_skills(db: AsyncSession, hero_id: int) -> list[BattleSkill]:
    learned = await get_hero_skills(db, hero_id)
    return [
        BattleSkill(
            skill_definition_id=cs.skill_definition.id,
            name=cs.skill_definition.name,
            skill_type=cs.skill_definition.skill_type.value,
            power=power_at_level(cs.skill_definition, cs.level),
            cooldown_turns=cs.skill_definition.cooldown_turns,
            sort_order=cs.skill_definition.sort_order,
            buff_stat=cs.skill_definition.buff_stat,
            is_interrupt=cs.skill_definition.is_interrupt,
        )
        for cs in learned
    ]


def _enemy_combat_stats(enemy: EnemyTemplate) -> CombatantStats:
    return CombatantStats(
        hp=enemy.hp,
        attack=enemy.attack,
        defense=enemy.defense,
        speed=enemy.speed,
        crit_chance=float(enemy.crit_chance),
        crit_damage=float(enemy.crit_damage),
    )


async def _fetch_by_idempotency_key(db: AsyncSession, user_id: int, idempotency_key: str) -> Optional[Battle]:
    result = await db.execute(
        select(Battle).where(Battle.user_id == user_id, Battle.idempotency_key == idempotency_key)
    )
    return result.unique().scalar_one_or_none()


async def start_battle(
    db: AsyncSession, user: User, hero: UserHero, enemy_template_id: int, idempotency_key: Optional[str]
) -> BattleOut:
    # Captured once, up front, as plain ints: a rollback later in this
    # function (the concurrent-idempotency-race path below) expires every
    # attribute SQLAlchemy was tracking on `user`/`hero` — INCLUDING their
    # primary keys, not just the mutated columns. Touching user.id/hero.id
    # after that rollback without an awaited refresh first raises
    # MissingGreenlet (confirmed live against real Postgres under genuine
    # concurrent requests; SQLite's tests can't reach this path at all —
    # see the skipped concurrency test). Using these plain ints sidesteps
    # the whole class of expired-attribute footguns.
    user_id, hero_id = user.id, hero.id

    if idempotency_key:
        existing = await _fetch_by_idempotency_key(db, user_id, idempotency_key)
        if existing is not None:
            return await _battle_to_out(db, existing, hero, user)

    enemy = await _get_enemy_or_404(db, enemy_template_id)
    _assert_enemy_available(enemy)

    if hero.level < enemy.level:
        raise ConflictError(
            "Hero level too low to challenge this enemy",
            details={"hero_level": hero.level, "required_hero_level": enemy.level},
        )

    hero_stats = await hero_combat_stats(db, hero)
    hero_skills = await hero_battle_skills(db, hero.id)
    enemy_stats = _enemy_combat_stats(enemy)

    outcome = simulate_battle(hero_stats, hero_skills, enemy_stats, random.Random())

    if outcome.won:
        final_hero, final_user = await grant_hero_reward(
            db,
            hero_id,
            user_id,
            enemy.reward_xp,
            enemy.reward_coins,
            TransactionType.battle_reward,
            f"Победа над {enemy.name}",
            related_object_type="enemy_template",
            related_object_id=enemy.id,
        )
        reward_xp, reward_coins = enemy.reward_xp, enemy.reward_coins
    else:
        reward_xp, reward_coins = 0, 0
        final_hero, final_user = hero, user

    battle = Battle(
        user_id=user_id,
        hero_id=hero_id,
        enemy_template_id=enemy.id,
        result=BattleResult.won if outcome.won else BattleResult.lost,
        turns=outcome.turns,
        log=outcome.log,
        reward_xp=reward_xp,
        reward_coins=reward_coins,
        idempotency_key=idempotency_key,
        created_at=datetime.now(timezone.utc),
    )
    db.add(battle)

    try:
        await db.commit()
    except IntegrityError:
        # Same race as chest_service.open_chest: two concurrent requests
        # with the same idempotency key. Roll back EVERYTHING this attempt
        # touched (XP, coins, the Battle row) and return the winner's
        # already-committed result instead of double-granting anything.
        await db.rollback()
        if idempotency_key:
            existing = await _fetch_by_idempotency_key(db, user_id, idempotency_key)
            if existing is not None:
                # db.rollback() expires every object this session was
                # tracking (including primary keys — see the user_id/hero_id
                # comment above), so hero/user must be re-fetched fresh
                # rather than touched directly. This also happens to be
                # exactly right semantically: _battle_to_out always shows
                # CURRENT state, and current means "as committed by the
                # winner" here.
                refreshed_hero = await db.get(UserHero, hero_id)
                refreshed_user = await db.get(User, user_id)
                return await _battle_to_out(db, existing, refreshed_hero, refreshed_user)
        raise

    return await _build_out(battle, final_hero, final_user)


async def _battle_to_out(db: AsyncSession, battle: Battle, hero: UserHero, user: User) -> BattleOut:
    """Used for GET /battles/{id}, GET /battles, and idempotent replays —
    always shows the hero/user's CURRENT level/xp/balance (not a frozen
    snapshot from when the battle happened), same as chest_service always
    returning the current balance rather than a stored one."""
    return await _build_out(battle, hero, user)


async def _build_out(battle: Battle, hero: UserHero, user: User) -> BattleOut:
    # hero_progress_out is the single shared computation of "current
    # level/xp/balance" (see its docstring) — pulled apart into this
    # response's own already-shipped flat field names rather than nesting
    # HeroProgressOut directly, so the response shape doesn't change.
    progress = hero_progress_out(hero, user)
    return BattleOut(
        id=battle.id,
        enemy=EnemySummaryOut(id=battle.enemy_template.id, name=battle.enemy_template.name, level=battle.enemy_template.level),
        result=battle.result.value,
        turns=battle.turns,
        log=[BattleLogEntryOut(**entry) for entry in battle.log],
        reward_xp=battle.reward_xp,
        reward_coins=battle.reward_coins,
        hero_level=progress.level,
        hero_xp=progress.xp,
        balance=progress.balance,
        created_at=battle.created_at.isoformat(),
    )


async def get_battle(db: AsyncSession, user: User, hero: UserHero, battle_id: int) -> BattleOut:
    result = await db.execute(select(Battle).where(Battle.id == battle_id, Battle.user_id == user.id))
    battle = result.unique().scalar_one_or_none()
    if battle is None:
        raise NotFoundError("Battle not found")
    return await _build_out(battle, hero, user)


async def list_battles(db: AsyncSession, user: User, hero: UserHero, limit: int = 50) -> list[BattleOut]:
    result = await db.execute(
        select(Battle).where(Battle.user_id == user.id).order_by(Battle.id.desc()).limit(limit)
    )
    battles = result.unique().scalars().all()
    return [await _build_out(b, hero, user) for b in battles]
