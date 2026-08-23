from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.security import create_admin_token
from app.database import get_db
from app.models.user import User
from app.schemas.auth import SessionResponse, UserMeOut
from app.services.hero_service import get_active_hero, hero_to_out
from app.services.referral_service import referral_count as get_referral_count

router = APIRouter()


async def _user_out(db: AsyncSession, user: User) -> UserMeOut:
    hero = await get_active_hero(db, user)
    return UserMeOut(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        active_hero=await hero_to_out(db, hero) if hero else None,
        referral_code=str(user.telegram_id),
        referral_count=await get_referral_count(db, user.id),
    )


@router.post("/session", response_model=SessionResponse)
async def create_session(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    admin_token = create_admin_token(user.id, user.telegram_id) if user.is_admin else None
    return SessionResponse(user=await _user_out(db, user), admin_token=admin_token)


@router.get("/me", response_model=UserMeOut)
async def get_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _user_out(db, user)
