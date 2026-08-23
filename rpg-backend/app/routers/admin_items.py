from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.item_affix import ItemAffix
from app.models.item_template import ItemTemplate
from app.schemas.admin import ItemTemplateAdminOut, ItemTemplateCreate, ItemTemplateUpdate
from app.services.image_service import delete_template_image, save_template_image

router = APIRouter(dependencies=[Depends(get_current_admin)])


async def _get_item_or_404(db: AsyncSession, item_id: int) -> ItemTemplate:
    result = await db.execute(select(ItemTemplate).where(ItemTemplate.id == item_id))
    item = result.unique().scalar_one_or_none()
    if item is None:
        raise NotFoundError("Item template not found")
    return item


@router.get("", response_model=list[ItemTemplateAdminOut])
async def list_all_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ItemTemplate).order_by(ItemTemplate.sort_order, ItemTemplate.id))
    return result.unique().scalars().all()


@router.post("", response_model=ItemTemplateAdminOut)
async def create_item(payload: ItemTemplateCreate, db: AsyncSession = Depends(get_db)):
    data = payload.model_dump(exclude={"affix_stat_types"})
    item = ItemTemplate(**data)
    db.add(item)
    await db.flush()
    for stat_type in payload.affix_stat_types:
        db.add(ItemAffix(item_template_id=item.id, stat_type=stat_type))
    await db.commit()
    return await _get_item_or_404(db, item.id)


@router.put("/{item_id}", response_model=ItemTemplateAdminOut)
async def update_item(item_id: int, payload: ItemTemplateUpdate, db: AsyncSession = Depends(get_db)):
    item = await _get_item_or_404(db, item_id)
    updates = payload.model_dump(exclude_unset=True, exclude={"affix_stat_types"})
    for key, value in updates.items():
        setattr(item, key, value)

    if payload.affix_stat_types is not None:
        # item.affixes.clear() would try to NULL out item_template_id
        # instead of deleting the rows — the relationship has no
        # cascade="all, delete-orphan" (unlike Chest.rarity_probabilities),
        # and that column is NOT NULL. Delete explicitly instead of relying
        # on ORM collection-removal cascade behavior, then expire the
        # relationship so the session drops its now-stale in-memory
        # references to the just-deleted rows before anything re-touches
        # `item.affixes` (a plain .clear()/append() after a raw bulk DELETE
        # trips "Instance has been deleted" on the old rows still tracked
        # in the collection).
        await db.execute(delete(ItemAffix).where(ItemAffix.item_template_id == item.id))
        db.expire(item, ["affixes"])
        await db.flush()
        for stat_type in payload.affix_stat_types:
            db.add(ItemAffix(item_template_id=item.id, stat_type=stat_type))

    db.add(item)
    await db.commit()
    return await _get_item_or_404(db, item_id)


@router.post("/{item_id}/toggle-active", response_model=ItemTemplateAdminOut)
async def toggle_item_active(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await _get_item_or_404(db, item_id)
    item.is_active = not item.is_active
    db.add(item)
    await db.commit()
    return await _get_item_or_404(db, item_id)


@router.post("/{item_id}/image", response_model=ItemTemplateAdminOut)
async def upload_item_image(item_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    item = await _get_item_or_404(db, item_id)
    old_path = item.image_path
    item.image_path = await save_template_image(file, "items", item.name)
    db.add(item)
    await db.commit()
    delete_template_image(old_path)
    return await _get_item_or_404(db, item_id)
