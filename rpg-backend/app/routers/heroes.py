from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.user import User
from app.schemas.character import CreateHeroRequest, UserHeroOut
from app.services.hero_service import create_hero, get_active_hero, hero_to_out

router = APIRouter()


@router.get("/me", response_model=UserHeroOut)
async def get_my_hero(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await get_active_hero(db, user)
    if hero is None:
        raise NotFoundError("You don't have a hero yet")
    return await hero_to_out(db, hero)


@router.post("", response_model=UserHeroOut, status_code=status.HTTP_201_CREATED)
async def choose_hero(
    payload: CreateHeroRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    hero = await create_hero(db, user.id, payload.hero_template_id, payload.name)
    return await hero_to_out(db, hero)
