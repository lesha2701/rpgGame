from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.profile import ProfileOut, PublicProfileOut
from app.services.profile_service import get_my_profile, get_public_profile

router = APIRouter()


@router.get("/me", response_model=ProfileOut)
async def get_my_profile_endpoint(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await get_my_profile(db, user)


@router.get("/{user_id}", response_model=PublicProfileOut)
async def get_public_profile_endpoint(
    user_id: int, _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await get_public_profile(db, user_id)
