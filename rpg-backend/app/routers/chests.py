from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.chest import Chest
from app.models.user import User
from app.models.user_item import UserItem
from app.schemas.chest import (
    ChestOpeningHistoryOut,
    ChestOpenResult,
    ChestOut,
    ChestSummaryOut,
    FreeChestStatusOut,
    OpenChestRequest,
)
from app.services.chest_service import chest_to_out, list_chests, list_openings, open_chest
from app.services.free_chest_service import claim as claim_free_chest
from app.services.free_chest_service import get_status as get_free_chest_status
from app.services.hero_service import get_active_hero
from app.services.inventory_service import item_template_to_out

router = APIRouter()


@router.get("", response_model=list[ChestOut])
async def list_all_chests(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    chests = await list_chests(db)
    return [chest_to_out(c) for c in chests]


@router.get("/openings", response_model=list[ChestOpeningHistoryOut])
async def get_opening_history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    openings = await list_openings(db, user.id)
    out = []
    for opening in openings:
        chest_row = await db.get(Chest, opening.chest_id)
        item_row = await db.get(UserItem, opening.reward_user_item_id)
        assert chest_row is not None and item_row is not None
        template_out = item_template_to_out(item_row.item_template)
        out.append(
            ChestOpeningHistoryOut(
                id=opening.id,
                chest=ChestSummaryOut(id=chest_row.id, name=chest_row.name),
                reward_item_id=item_row.id,
                reward_item_name=template_out.name,
                reward_rarity=template_out.rarity,
                price_paid=opening.price_paid,
                created_at=opening.created_at.isoformat(),
            )
        )
    return out


@router.get("/free", response_model=FreeChestStatusOut)
async def get_free_chest(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await get_free_chest_status(db, user)


@router.post("/free/claim", response_model=ChestOpenResult)
async def claim_free_chest_endpoint(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await get_active_hero(db, user)
    if hero is None:
        raise NotFoundError("You don't have a hero yet")
    return await claim_free_chest(db, user, hero)


@router.get("/{chest_id}", response_model=ChestOut)
async def get_chest_detail(chest_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    chests = await list_chests(db)
    chest = next((c for c in chests if c.id == chest_id), None)
    if chest is None:
        raise NotFoundError("Chest not found")
    return chest_to_out(chest)


@router.post("/{chest_id}/open", response_model=ChestOpenResult)
async def open_chest_endpoint(
    chest_id: int,
    payload: OpenChestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    hero = await get_active_hero(db, user)
    if hero is None:
        raise NotFoundError("You don't have a hero yet")
    return await open_chest(db, user, hero, chest_id, payload.idempotency_key)
