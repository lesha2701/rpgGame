from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.app_icon import AppIcon
from app.schemas.app_icon import AppIconAdminOut
from app.services.image_service import delete_template_image, save_template_image

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("", response_model=list[AppIconAdminOut])
async def list_all_app_icons(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppIcon).order_by(AppIcon.key))
    return result.scalars().all()


@router.post("/{app_icon_id}/image", response_model=AppIconAdminOut)
async def upload_app_icon_image(app_icon_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppIcon).where(AppIcon.id == app_icon_id))
    icon = result.scalar_one_or_none()
    if icon is None:
        raise NotFoundError("Icon slot not found")

    old_path = icon.image_path
    icon.image_path = await save_template_image(file, "app_icons", icon.key)
    db.add(icon)
    await db.commit()
    await db.refresh(icon)
    delete_template_image(old_path)
    return icon
