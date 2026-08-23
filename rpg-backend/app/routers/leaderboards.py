from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.leaderboard import LeaderboardOut
from app.services.leaderboard_service import get_leaderboard

router = APIRouter()

LeaderboardType = Literal["level", "pve_wins", "arena_wins", "coins"]


@router.get("/{leaderboard_type}", response_model=LeaderboardOut)
async def get_leaderboard_endpoint(
    leaderboard_type: LeaderboardType,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_leaderboard(db, leaderboard_type, limit, offset, user.id)
