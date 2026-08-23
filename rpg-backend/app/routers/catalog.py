from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.character_class import CharacterClass
from app.models.hero_template import HeroTemplate
from app.models.race import Race
from app.schemas.character import CharacterClassOut, HeroTemplateOut, RaceOut

router = APIRouter()


@router.get("/races", response_model=list[RaceOut])
async def list_races(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Race).where(Race.is_active.is_(True)).order_by(Race.sort_order, Race.id))
    return result.scalars().all()


@router.get("/classes", response_model=list[CharacterClassOut])
async def list_classes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CharacterClass)
        .where(CharacterClass.is_active.is_(True))
        .order_by(CharacterClass.sort_order, CharacterClass.id)
    )
    return result.scalars().all()


@router.get("/hero-templates", response_model=list[HeroTemplateOut])
async def list_hero_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(HeroTemplate)
        .where(HeroTemplate.is_active.is_(True))
        .order_by(HeroTemplate.sort_order, HeroTemplate.id)
    )
    return result.scalars().all()
