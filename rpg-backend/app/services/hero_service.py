from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.hero_template import HeroTemplate
from app.models.user import User
from app.models.user_hero import UserHero
from app.models.user_item import UserItem
from app.schemas.character import HeroStatsOut, HeroTemplateOut, UserHeroOut
from app.schemas.common import HeroProgressOut
from app.services.item_progression import ItemStatBundle, compute_item_stats
from app.services.progression import LevelUpResult, apply_xp_gain, compute_stats, visual_stage_for_level, xp_to_next_level
from app.services.wallet_service import lock_user_for_update


async def _fetch_hero(db: AsyncSession, hero_id: int) -> UserHero | None:
    result = await db.execute(select(UserHero).where(UserHero.id == hero_id))
    return result.scalar_one_or_none()


async def lock_hero_for_update(db: AsyncSession, hero_id: int) -> UserHero:
    """SELECT ... FOR UPDATE, scoped to just user_heroes via of=UserHero.

    UserHero.hero_template is lazy="joined", so a plain FOR UPDATE on this
    query would try to lock hero_templates too through that join — and
    Postgres rejects FOR UPDATE on the nullable side of an outer join,
    which is exactly the shape SQLAlchemy's joined eager loading uses. The
    of=UserHero (mirroring the football app's wallet_service pattern for
    the same reason with User.active_badge) keeps the lock scoped to the
    row actually being mutated."""
    result = await db.execute(
        select(UserHero)
        .where(UserHero.id == hero_id)
        .with_for_update(of=UserHero)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def get_active_hero(db: AsyncSession, user: User) -> UserHero | None:
    if user.active_hero_id is None:
        return None
    return await _fetch_hero(db, user.active_hero_id)


async def create_hero(db: AsyncSession, user_id: int, hero_template_id: int, name: str) -> UserHero:
    """V1 allows exactly one hero per user, enforced here (not a DB
    constraint) precisely so a later stage can lift the restriction without
    a migration — see UserHero's docstring."""
    locked_user = await lock_user_for_update(db, user_id)
    if locked_user.active_hero_id is not None:
        raise ConflictError("You already have a hero", details={"active_hero_id": locked_user.active_hero_id})

    template = await db.get(HeroTemplate, hero_template_id)
    if template is None or not template.is_active:
        raise NotFoundError("Hero template not found")

    hero = UserHero(user_id=user_id, hero_template_id=hero_template_id, name=name, level=1, xp=0)
    db.add(hero)
    await db.flush()

    locked_user.active_hero_id = hero.id
    db.add(locked_user)
    await db.commit()

    created = await _fetch_hero(db, hero.id)
    assert created is not None
    return created


async def grant_xp(db: AsyncSession, hero_id: int, amount: int) -> tuple[UserHero, LevelUpResult]:
    """The one place that mutates level/xp. Transactionally composable by
    design: does NOT commit (or rollback) — it only locks the hero row and
    mutates it within whatever transaction the caller already has open, the
    same way wallet_service.credit_coins/debit_coins never commit either.
    The caller commits once, after every mutation for the operation has
    been applied (e.g. battle_service.start_battle folds this together with
    credit_coins and creating the Battle row into one atomic commit — XP
    must not land if the coins or the battle record don't).

    Row-locked (via lock_hero_for_update) so two concurrent XP grants for
    the same hero can't race and drop one of them, regardless of whether
    the caller's transaction also touches other rows."""
    if amount < 0:
        raise ValueError("amount must not be negative")

    locked_hero = await lock_hero_for_update(db, hero_id)
    result = apply_xp_gain(locked_hero.level, locked_hero.xp, amount)
    locked_hero.level = result.level
    locked_hero.xp = result.xp
    db.add(locked_hero)

    return locked_hero, result


def hero_progress_out(hero: UserHero, user: User) -> HeroProgressOut:
    """The one function that builds a hero+wallet snapshot — Battle/
    Expedition/Quest claim responses all need "current level/xp/balance",
    and this is the single place that composes it (see schemas/common.py's
    HeroProgressOut docstring for why existing endpoints don't switch their
    own response shape to use this type directly)."""
    return HeroProgressOut(
        level=hero.level, xp=hero.xp, xp_to_next_level=xp_to_next_level(hero.level), balance=user.balance
    )


async def _equipped_item_stats_total(db: AsyncSession, hero_id: int) -> ItemStatBundle:
    """Not in inventory_service.py on purpose: inventory_service imports
    lock_hero_for_update from this module, so importing inventory_service
    back from here would be circular. item_progression (pure formulas) and
    the UserItem model have no such constraint."""
    result = await db.execute(select(UserItem).where(UserItem.equipped_hero_id == hero_id))
    total = ItemStatBundle()
    for item in result.unique().scalars().all():
        template = item.item_template
        total = total + compute_item_stats(
            template.slot, template.tier, template.rarity, [a.stat_type for a in template.affixes]
        )
    return total


async def hero_to_out(db: AsyncSession, hero: UserHero) -> UserHeroOut:
    """Final stats = class base + level progression (compute_stats) +
    equipped item bonuses (_equipped_item_stats_total) — composed fresh on
    every call, never persisted, so equip/unequip/level-up can never leave
    a stale stat number lying around (requirement: don't store a value that
    can desync)."""
    class_stats = compute_stats(hero.hero_template.character_class, hero.level)
    item_stats = await _equipped_item_stats_total(db, hero.id)
    return UserHeroOut(
        id=hero.id,
        name=hero.name or hero.hero_template.name,
        level=hero.level,
        xp=hero.xp,
        xp_to_next_level=xp_to_next_level(hero.level),
        visual_stage=visual_stage_for_level(hero.level),
        hero_template=HeroTemplateOut.model_validate(hero.hero_template),
        stats=HeroStatsOut(
            # Rounded once, here, at the final combined total — item_power's
            # tier/rarity math is naturally fractional (geometric growth,
            # weighted splits), and rounding each item's contribution
            # separately before summing would compound error across up to 7
            # equipped items. hp/attack/defense/speed are whole-number
            # display stats; crit_chance/crit_damage stay float (fractions).
            hp=round(class_stats.hp + item_stats.hp),
            attack=round(class_stats.attack + item_stats.attack),
            defense=round(class_stats.defense + item_stats.defense),
            speed=round(class_stats.speed + item_stats.speed),
            crit_chance=class_stats.crit_chance,
            crit_damage=class_stats.crit_damage,
        ),
    )
