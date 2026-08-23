from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.character_class import CharacterClass
from app.schemas.admin import CharacterClassAdminOut, CharacterClassCreate, CharacterClassUpdate

router = APIRouter(dependencies=[Depends(get_current_admin)])


async def _get_class_or_404(db: AsyncSession, class_id: int) -> CharacterClass:
    result = await db.execute(select(CharacterClass).where(CharacterClass.id == class_id))
    char_class = result.scalar_one_or_none()
    if char_class is None:
        raise NotFoundError("Class not found")
    return char_class


@router.get("", response_model=list[CharacterClassAdminOut])
async def list_all_classes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CharacterClass).order_by(CharacterClass.sort_order, CharacterClass.id))
    return result.scalars().all()


@router.post("", response_model=CharacterClassAdminOut)
async def create_class(payload: CharacterClassCreate, db: AsyncSession = Depends(get_db)):
    char_class = CharacterClass(**payload.model_dump())
    db.add(char_class)
    await db.commit()
    await db.refresh(char_class)
    return char_class


@router.put("/{class_id}", response_model=CharacterClassAdminOut)
async def update_class(class_id: int, payload: CharacterClassUpdate, db: AsyncSession = Depends(get_db)):
    char_class = await _get_class_or_404(db, class_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(char_class, key, value)
    db.add(char_class)
    await db.commit()
    await db.refresh(char_class)
    return char_class


@router.post("/{class_id}/toggle-active", response_model=CharacterClassAdminOut)
async def toggle_class_active(class_id: int, db: AsyncSession = Depends(get_db)):
    char_class = await _get_class_or_404(db, class_id)
    char_class.is_active = not char_class.is_active
    db.add(char_class)
    await db.commit()
    await db.refresh(char_class)
    return char_class
