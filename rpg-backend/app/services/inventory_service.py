from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import EquipmentSlot
from app.models.item_template import ItemTemplate
from app.models.user_item import UserItem
from app.schemas.item import ItemAffixOut, ItemStatsOut, ItemTemplateOut, UserItemOut
from app.services.hero_service import lock_hero_for_update
from app.services.item_progression import compute_item_stats, required_level_for_tier


def item_template_to_out(template: ItemTemplate) -> ItemTemplateOut:
    stats = compute_item_stats(template.slot, template.tier, template.rarity, [a.stat_type for a in template.affixes])
    return ItemTemplateOut(
        id=template.id,
        slot=template.slot.value,
        tier=template.tier,
        rarity=template.rarity.value,
        name=template.name,
        description=template.description,
        image_path=template.image_path,
        required_hero_level=required_level_for_tier(template.tier),
        stats=ItemStatsOut(hp=stats.hp, attack=stats.attack, defense=stats.defense, speed=stats.speed),
        affixes=[ItemAffixOut.model_validate(a) for a in template.affixes],
    )


def user_item_to_out(item: UserItem) -> UserItemOut:
    return UserItemOut(
        id=item.id,
        item_template=item_template_to_out(item.item_template),
        is_equipped=item.equipped_hero_id is not None,
        equipped_hero_id=item.equipped_hero_id,
    )


async def _fetch_user_item(db: AsyncSession, user_item_id: int) -> UserItem | None:
    # .unique() is required whenever a query's result touches ItemTemplate
    # (directly or via UserItem.item_template) — ItemTemplate.affixes is a
    # lazy="joined" *collection*, and SQLAlchemy refuses to hydrate ORM rows
    # from a joined-collection query without an explicit .unique() to
    # de-duplicate the parent rows the JOIN multiplies.
    result = await db.execute(select(UserItem).where(UserItem.id == user_item_id))
    return result.unique().scalar_one_or_none()


async def list_item_templates(
    db: AsyncSession, tier: int | None = None, slot: EquipmentSlot | None = None
) -> list[ItemTemplate]:
    query = select(ItemTemplate).where(ItemTemplate.is_active.is_(True))
    if tier is not None:
        query = query.where(ItemTemplate.tier == tier)
    if slot is not None:
        query = query.where(ItemTemplate.slot == slot)
    result = await db.execute(query.order_by(ItemTemplate.tier, ItemTemplate.slot, ItemTemplate.sort_order))
    return list(result.unique().scalars().all())


async def get_inventory(db: AsyncSession, user_id: int) -> list[UserItem]:
    result = await db.execute(select(UserItem).where(UserItem.owner_user_id == user_id).order_by(UserItem.id))
    return list(result.unique().scalars().all())


async def get_equipped_items(db: AsyncSession, hero_id: int) -> list[UserItem]:
    result = await db.execute(
        select(UserItem).where(UserItem.equipped_hero_id == hero_id).order_by(UserItem.slot)
    )
    return list(result.unique().scalars().all())


async def grant_item(db: AsyncSession, user_id: int, item_template_id: int) -> UserItem:
    """Adds an item to a user's inventory, unequipped. Not exposed over
    HTTP in Stage 4 — there is no legitimate way to acquire an item yet
    (chests/drops are Stage 5); this is the primitive that will call.
    Used directly by seed.py and for manual verification."""
    template = await db.get(ItemTemplate, item_template_id)
    if template is None or not template.is_active:
        raise NotFoundError("Item template not found")

    item = UserItem(owner_user_id=user_id, item_template_id=item_template_id, slot=template.slot)
    db.add(item)
    await db.commit()

    created = await _fetch_user_item(db, item.id)
    assert created is not None
    return created


async def equip_item(db: AsyncSession, hero_id: int, user_item_id: int) -> UserItem:
    """Locks the hero (not just the item) — the invariant being protected,
    "at most one equipped item per slot on this hero", spans every item
    that could occupy that slot, not just the one being equipped, so two
    concurrent equips into the same slot must serialize against each
    other regardless of which UserItem row each one targets."""
    locked_hero = await lock_hero_for_update(db, hero_id)

    item = await _fetch_user_item(db, user_item_id)
    if item is None or item.owner_user_id != locked_hero.user_id:
        raise NotFoundError("Item not found in your inventory")

    if item.equipped_hero_id == hero_id:
        return item  # already equipped here — idempotent no-op

    if item.equipped_hero_id is not None:
        raise ConflictError("Item is already equipped on another hero")

    required_level = required_level_for_tier(item.item_template.tier)
    if locked_hero.level < required_level:
        raise ConflictError(
            "Hero level too low to equip this item",
            details={"hero_level": locked_hero.level, "required_hero_level": required_level},
        )

    # Auto-swap: unequip whatever currently occupies this slot on this hero.
    result = await db.execute(
        select(UserItem).where(UserItem.equipped_hero_id == hero_id, UserItem.slot == item.slot)
    )
    previously_equipped = result.unique().scalar_one_or_none()
    if previously_equipped is not None:
        previously_equipped.equipped_hero_id = None
        db.add(previously_equipped)

    item.equipped_hero_id = hero_id
    db.add(item)
    await db.commit()

    refreshed = await _fetch_user_item(db, user_item_id)
    assert refreshed is not None
    return refreshed


async def unequip_item(db: AsyncSession, hero_id: int, user_item_id: int) -> UserItem:
    locked_hero = await lock_hero_for_update(db, hero_id)

    item = await _fetch_user_item(db, user_item_id)
    if item is None or item.equipped_hero_id != locked_hero.id:
        raise NotFoundError("Equipped item not found on this hero")

    item.equipped_hero_id = None
    db.add(item)
    await db.commit()

    refreshed = await _fetch_user_item(db, user_item_id)
    assert refreshed is not None
    return refreshed
