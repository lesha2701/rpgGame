from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.hero_template import HeroTemplate
from app.schemas.admin import HeroTemplateAdminOut, HeroTemplateCreate, HeroTemplateUpdate
from app.services.image_service import delete_template_image, save_template_image

router = APIRouter(dependencies=[Depends(get_current_admin)])


async def _get_template_or_404(db: AsyncSession, template_id: int) -> HeroTemplate:
    # race/character_class are lazy="joined" on this model, so a plain
    # select already eager-loads them — re-fetching after a mutation (like
    # admin_chests.py does) is simpler and safer here than db.refresh(),
    # which doesn't reload relationships by default.
    result = await db.execute(select(HeroTemplate).where(HeroTemplate.id == template_id))
    template = result.unique().scalar_one_or_none()
    if template is None:
        raise NotFoundError("Hero template not found")
    return template


@router.get("", response_model=list[HeroTemplateAdminOut])
async def list_all_hero_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(HeroTemplate).order_by(HeroTemplate.sort_order, HeroTemplate.id))
    return result.unique().scalars().all()


@router.post("", response_model=HeroTemplateAdminOut)
async def create_hero_template(payload: HeroTemplateCreate, db: AsyncSession = Depends(get_db)):
    template = HeroTemplate(**payload.model_dump())
    db.add(template)
    await db.commit()
    return await _get_template_or_404(db, template.id)


@router.put("/{template_id}", response_model=HeroTemplateAdminOut)
async def update_hero_template(template_id: int, payload: HeroTemplateUpdate, db: AsyncSession = Depends(get_db)):
    template = await _get_template_or_404(db, template_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, key, value)
    db.add(template)
    await db.commit()
    return await _get_template_or_404(db, template_id)


@router.post("/{template_id}/toggle-active", response_model=HeroTemplateAdminOut)
async def toggle_hero_template_active(template_id: int, db: AsyncSession = Depends(get_db)):
    template = await _get_template_or_404(db, template_id)
    template.is_active = not template.is_active
    db.add(template)
    await db.commit()
    return await _get_template_or_404(db, template_id)


@router.post("/{template_id}/image", response_model=HeroTemplateAdminOut)
async def upload_hero_template_image(
    template_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    template = await _get_template_or_404(db, template_id)
    old_path = template.image_path
    template.image_path = await save_template_image(file, "heroes", template.name)
    db.add(template)
    await db.commit()
    delete_template_image(old_path)
    return await _get_template_or_404(db, template_id)
