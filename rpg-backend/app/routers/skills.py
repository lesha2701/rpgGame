from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.user import User
from app.schemas.skill import AvailableSkillsOut, CharacterSkillOut
from app.services.hero_service import get_active_hero
from app.services.skill_service import character_skill_to_out, get_available_skills_out, get_hero_skills, upgrade_skill

router = APIRouter()


async def _require_active_hero(db: AsyncSession, user: User):
    hero = await get_active_hero(db, user)
    if hero is None:
        raise NotFoundError("You don't have a hero yet")
    return hero


@router.get("", response_model=list[CharacterSkillOut])
async def list_my_skills(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await _require_active_hero(db, user)
    skills = await get_hero_skills(db, hero.id)
    return [character_skill_to_out(s) for s in skills]


@router.get("/available", response_model=AvailableSkillsOut)
async def list_available_skills(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await _require_active_hero(db, user)
    return await get_available_skills_out(db, hero)


@router.post("/{skill_definition_id}/upgrade", response_model=CharacterSkillOut)
async def upgrade_my_skill(
    skill_definition_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    hero = await _require_active_hero(db, user)
    skill = await upgrade_skill(db, hero.id, skill_definition_id)
    return character_skill_to_out(skill)
