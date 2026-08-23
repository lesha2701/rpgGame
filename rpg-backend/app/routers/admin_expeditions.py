from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.expedition_template import ExpeditionTemplate
from app.schemas.admin import ExpeditionTemplateAdminOut, ExpeditionTemplateCreate, ExpeditionTemplateUpdate
from app.services.image_service import delete_template_image, save_template_image

router = APIRouter(dependencies=[Depends(get_current_admin)])


async def _get_expedition_or_404(db: AsyncSession, expedition_id: int) -> ExpeditionTemplate:
    result = await db.execute(select(ExpeditionTemplate).where(ExpeditionTemplate.id == expedition_id))
    expedition = result.scalar_one_or_none()
    if expedition is None:
        raise NotFoundError("Expedition template not found")
    return expedition


@router.get("", response_model=list[ExpeditionTemplateAdminOut])
async def list_all_expeditions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ExpeditionTemplate).order_by(ExpeditionTemplate.sort_order, ExpeditionTemplate.id))
    return result.scalars().all()


@router.post("", response_model=ExpeditionTemplateAdminOut)
async def create_expedition(payload: ExpeditionTemplateCreate, db: AsyncSession = Depends(get_db)):
    expedition = ExpeditionTemplate(**payload.model_dump())
    db.add(expedition)
    await db.commit()
    await db.refresh(expedition)
    return expedition


@router.put("/{expedition_id}", response_model=ExpeditionTemplateAdminOut)
async def update_expedition(expedition_id: int, payload: ExpeditionTemplateUpdate, db: AsyncSession = Depends(get_db)):
    expedition = await _get_expedition_or_404(db, expedition_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(expedition, key, value)
    db.add(expedition)
    await db.commit()
    await db.refresh(expedition)
    return expedition


@router.post("/{expedition_id}/toggle-active", response_model=ExpeditionTemplateAdminOut)
async def toggle_expedition_active(expedition_id: int, db: AsyncSession = Depends(get_db)):
    expedition = await _get_expedition_or_404(db, expedition_id)
    expedition.is_active = not expedition.is_active
    db.add(expedition)
    await db.commit()
    await db.refresh(expedition)
    return expedition


@router.post("/{expedition_id}/image", response_model=ExpeditionTemplateAdminOut)
async def upload_expedition_image(
    expedition_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    expedition = await _get_expedition_or_404(db, expedition_id)
    old_path = expedition.image_path
    expedition.image_path = await save_template_image(file, "expeditions", expedition.name)
    db.add(expedition)
    await db.commit()
    await db.refresh(expedition)
    delete_template_image(old_path)
    return expedition
