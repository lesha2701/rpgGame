"""Structurally adapted from the football app's app/routers/admin_packs.py
— same shape (list/create/update/toggle-active, probability-sum validation)
trimmed for Stage 5. Image upload was added in a later pass (see
image_service.py's "chests" ResourceKind), matching the other four
resources' upload endpoints. Still missing: an admin action audit log
(AdminAction — Stage 13's full admin panel is the right place to port
that), and a Monte-Carlo preview endpoint."""

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin
from app.core.exceptions import ConflictError, NotFoundError
from app.database import get_db
from app.models.chest import Chest, ChestRarityProbability
from app.models.enums import Rarity
from app.schemas.chest import ChestCreate, ChestOut, ChestUpdate
from app.services.chest_service import chest_to_out
from app.services.image_service import delete_template_image, save_template_image

router = APIRouter(dependencies=[Depends(get_current_admin)])


def _validate_probabilities(rarity_probabilities: list) -> None:
    total = sum(p.probability for p in rarity_probabilities)
    if not (0.98 <= total <= 1.02):
        raise ConflictError(f"Rarity probabilities must sum to 1.0 (got {total:.4f})")


async def _get_chest_or_404(db: AsyncSession, chest_id: int) -> Chest:
    result = await db.execute(select(Chest).where(Chest.id == chest_id))
    chest = result.unique().scalar_one_or_none()
    if chest is None:
        raise NotFoundError("Chest not found")
    return chest


@router.get("", response_model=list[ChestOut])
async def list_all_chests_admin(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Chest).order_by(Chest.sort_order))
    chests = result.unique().scalars().all()
    return [chest_to_out(c) for c in chests]


@router.post("", response_model=ChestOut)
async def create_chest(payload: ChestCreate, db: AsyncSession = Depends(get_db)):
    _validate_probabilities(payload.rarity_probabilities)
    data = payload.model_dump(exclude={"rarity_probabilities", "guaranteed_min_rarity"})
    chest = Chest(
        **data,
        guaranteed_min_rarity=Rarity(payload.guaranteed_min_rarity) if payload.guaranteed_min_rarity else None,
    )
    db.add(chest)
    await db.flush()
    for rp in payload.rarity_probabilities:
        db.add(ChestRarityProbability(chest_id=chest.id, rarity=Rarity(rp.rarity), probability=rp.probability))
    await db.commit()
    chest = await _get_chest_or_404(db, chest.id)
    return chest_to_out(chest)


@router.put("/{chest_id}", response_model=ChestOut)
async def update_chest(chest_id: int, payload: ChestUpdate, db: AsyncSession = Depends(get_db)):
    chest = await _get_chest_or_404(db, chest_id)

    updates = payload.model_dump(exclude_unset=True, exclude={"rarity_probabilities", "guaranteed_min_rarity"})
    for key, value in updates.items():
        setattr(chest, key, value)
    if "guaranteed_min_rarity" in payload.model_fields_set:
        chest.guaranteed_min_rarity = Rarity(payload.guaranteed_min_rarity) if payload.guaranteed_min_rarity else None

    if payload.rarity_probabilities is not None:
        _validate_probabilities(payload.rarity_probabilities)
        chest.rarity_probabilities.clear()
        await db.flush()
        for rp in payload.rarity_probabilities:
            chest.rarity_probabilities.append(ChestRarityProbability(rarity=Rarity(rp.rarity), probability=rp.probability))

    db.add(chest)
    await db.commit()
    chest = await _get_chest_or_404(db, chest_id)
    return chest_to_out(chest)


@router.post("/{chest_id}/toggle-active", response_model=ChestOut)
async def toggle_chest_active(chest_id: int, db: AsyncSession = Depends(get_db)):
    chest = await _get_chest_or_404(db, chest_id)
    chest.is_active = not chest.is_active
    db.add(chest)
    await db.commit()
    chest = await _get_chest_or_404(db, chest_id)
    return chest_to_out(chest)


@router.post("/{chest_id}/image", response_model=ChestOut)
async def upload_chest_image(chest_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    chest = await _get_chest_or_404(db, chest_id)
    old_path = chest.image_path
    chest.image_path = await save_template_image(file, "chests", chest.name)
    db.add(chest)
    await db.commit()
    delete_template_image(old_path)
    chest = await _get_chest_or_404(db, chest_id)
    return chest_to_out(chest)
