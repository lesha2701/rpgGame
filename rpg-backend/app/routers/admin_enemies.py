from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.enemy_template import EnemyTemplate
from app.schemas.admin import EnemyTemplateAdminOut, EnemyTemplateCreate, EnemyTemplateUpdate
from app.services.image_service import delete_template_image, save_template_image

router = APIRouter(dependencies=[Depends(get_current_admin)])


async def _get_enemy_or_404(db: AsyncSession, enemy_id: int) -> EnemyTemplate:
    result = await db.execute(select(EnemyTemplate).where(EnemyTemplate.id == enemy_id))
    enemy = result.scalar_one_or_none()
    if enemy is None:
        raise NotFoundError("Enemy template not found")
    return enemy


@router.get("", response_model=list[EnemyTemplateAdminOut])
async def list_all_enemies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EnemyTemplate).order_by(EnemyTemplate.sort_order, EnemyTemplate.id))
    return result.scalars().all()


@router.post("", response_model=EnemyTemplateAdminOut)
async def create_enemy(payload: EnemyTemplateCreate, db: AsyncSession = Depends(get_db)):
    enemy = EnemyTemplate(**payload.model_dump())
    db.add(enemy)
    await db.commit()
    await db.refresh(enemy)
    return enemy


@router.put("/{enemy_id}", response_model=EnemyTemplateAdminOut)
async def update_enemy(enemy_id: int, payload: EnemyTemplateUpdate, db: AsyncSession = Depends(get_db)):
    enemy = await _get_enemy_or_404(db, enemy_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(enemy, key, value)
    db.add(enemy)
    await db.commit()
    await db.refresh(enemy)
    return enemy


@router.post("/{enemy_id}/toggle-active", response_model=EnemyTemplateAdminOut)
async def toggle_enemy_active(enemy_id: int, db: AsyncSession = Depends(get_db)):
    enemy = await _get_enemy_or_404(db, enemy_id)
    enemy.is_active = not enemy.is_active
    db.add(enemy)
    await db.commit()
    await db.refresh(enemy)
    return enemy


@router.post("/{enemy_id}/image", response_model=EnemyTemplateAdminOut)
async def upload_enemy_image(enemy_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    enemy = await _get_enemy_or_404(db, enemy_id)
    old_path = enemy.image_path
    enemy.image_path = await save_template_image(file, "enemies", enemy.name)
    db.add(enemy)
    await db.commit()
    await db.refresh(enemy)
    delete_template_image(old_path)
    return enemy
