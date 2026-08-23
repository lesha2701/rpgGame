from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.user import User
from app.schemas.enemy import EnemyOut
from app.services.battle_service import enemy_to_out, list_enemies
from app.services.hero_service import get_active_hero

router = APIRouter()


async def _hero_level_or_none(db: AsyncSession, user: User) -> int | None:
    hero = await get_active_hero(db, user)
    return hero.level if hero else None


@router.get("", response_model=list[EnemyOut])
async def list_all_enemies(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero_level = await _hero_level_or_none(db, user)
    enemies = await list_enemies(db)
    return [enemy_to_out(e, hero_level) for e in enemies]


@router.get("/{enemy_id}", response_model=EnemyOut)
async def get_enemy_detail(enemy_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero_level = await _hero_level_or_none(db, user)
    enemies = await list_enemies(db)
    enemy = next((e for e in enemies if e.id == enemy_id), None)
    if enemy is None:
        raise NotFoundError("Enemy not found")
    return enemy_to_out(enemy, hero_level)
