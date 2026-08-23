from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.app_icon import AppIcon
from app.schemas.app_icon import AppIconOut

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[AppIconOut])
async def list_app_icons(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppIcon))
    return result.scalars().all()
