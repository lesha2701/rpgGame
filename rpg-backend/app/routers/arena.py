from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.user import User
from app.schemas.arena import ArenaActionRequest, ArenaMatchOut, StartArenaMatchRequest
from app.services.arena_service import create_match, get_match, list_matches, submit_action
from app.services.hero_service import get_active_hero

router = APIRouter()


async def _require_active_hero(db: AsyncSession, user: User):
    hero = await get_active_hero(db, user)
    if hero is None:
        raise NotFoundError("You don't have a hero yet")
    return hero


@router.post("", response_model=ArenaMatchOut, status_code=201)
async def create_match_endpoint(
    payload: StartArenaMatchRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    hero = await _require_active_hero(db, user)
    return await create_match(db, user, hero, payload.opponent_user_id)


@router.get("", response_model=list[ArenaMatchOut])
async def list_matches_endpoint(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await list_matches(db, user)


@router.get("/{match_id}", response_model=ArenaMatchOut)
async def get_match_endpoint(match_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await get_match(db, user, match_id)


@router.post("/{match_id}/action", response_model=ArenaMatchOut)
async def submit_action_endpoint(
    match_id: int,
    payload: ArenaActionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await submit_action(db, user, match_id, payload.round, payload.action_type, payload.skill_id)
