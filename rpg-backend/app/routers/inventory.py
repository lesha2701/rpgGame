from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.user import User
from app.schemas.item import EquippedItemsOut, UserItemOut
from app.services.hero_service import get_active_hero
from app.services.inventory_service import (
    equip_item,
    get_equipped_items,
    get_inventory,
    unequip_item,
    user_item_to_out,
)

router = APIRouter()


async def _require_active_hero(db: AsyncSession, user: User):
    hero = await get_active_hero(db, user)
    if hero is None:
        raise NotFoundError("You don't have a hero yet")
    return hero


@router.get("/inventory", response_model=list[UserItemOut])
async def list_inventory(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    items = await get_inventory(db, user.id)
    return [user_item_to_out(i) for i in items]


@router.get("/inventory/{user_item_id}", response_model=UserItemOut)
async def get_inventory_item(
    user_item_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    items = await get_inventory(db, user.id)
    matching = next((i for i in items if i.id == user_item_id), None)
    if matching is None:
        raise NotFoundError("Item not found in your inventory")
    return user_item_to_out(matching)


@router.get("/equipment", response_model=EquippedItemsOut)
async def list_equipment(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await _require_active_hero(db, user)
    equipped = await get_equipped_items(db, hero.id)
    by_slot = {item.slot.value: user_item_to_out(item) for item in equipped}
    return EquippedItemsOut(**by_slot)


@router.post("/equipment/{user_item_id}/equip", response_model=UserItemOut)
async def equip(user_item_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await _require_active_hero(db, user)
    item = await equip_item(db, hero.id, user_item_id)
    return user_item_to_out(item)


@router.post("/equipment/{user_item_id}/unequip", response_model=UserItemOut)
async def unequip(user_item_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await _require_active_hero(db, user)
    item = await unequip_item(db, hero.id, user_item_id)
    return user_item_to_out(item)
