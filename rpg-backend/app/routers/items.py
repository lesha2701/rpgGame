from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.enums import EquipmentSlot
from app.schemas.item import ItemTemplateOut
from app.services.inventory_service import item_template_to_out, list_item_templates

router = APIRouter()


@router.get("", response_model=list[ItemTemplateOut])
async def list_items(
    tier: int | None = Query(default=None, ge=1, le=10),
    slot: EquipmentSlot | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    templates = await list_item_templates(db, tier=tier, slot=slot)
    return [item_template_to_out(t) for t in templates]
