from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.user import User
from app.schemas.battle import BattleOut, StartBattleRequest
from app.services.battle_service import get_battle, list_battles, start_battle
from app.services.hero_service import get_active_hero

router = APIRouter()


async def _require_active_hero(db: AsyncSession, user: User):
    hero = await get_active_hero(db, user)
    if hero is None:
        raise NotFoundError("You don't have a hero yet")
    return hero


@router.post("", response_model=BattleOut, status_code=201)
async def start_battle_endpoint(
    payload: StartBattleRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    hero = await _require_active_hero(db, user)
    return await start_battle(db, user, hero, payload.enemy_template_id, payload.idempotency_key)


@router.get("", response_model=list[BattleOut])
async def list_battle_history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await _require_active_hero(db, user)
    return await list_battles(db, user, hero)


@router.get("/{battle_id}", response_model=BattleOut)
async def get_battle_detail(
    battle_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    hero = await _require_active_hero(db, user)
    return await get_battle(db, user, hero, battle_id)
