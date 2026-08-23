"""Structurally identical to admin_chests.py — list/create/update/toggle,
no image upload (no static-asset serving in this backend yet)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.race import Race
from app.schemas.admin import RaceAdminOut, RaceCreate, RaceUpdate

router = APIRouter(dependencies=[Depends(get_current_admin)])


async def _get_race_or_404(db: AsyncSession, race_id: int) -> Race:
    result = await db.execute(select(Race).where(Race.id == race_id))
    race = result.scalar_one_or_none()
    if race is None:
        raise NotFoundError("Race not found")
    return race


@router.get("", response_model=list[RaceAdminOut])
async def list_all_races(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Race).order_by(Race.sort_order, Race.id))
    return result.scalars().all()


@router.post("", response_model=RaceAdminOut)
async def create_race(payload: RaceCreate, db: AsyncSession = Depends(get_db)):
    race = Race(**payload.model_dump())
    db.add(race)
    await db.commit()
    await db.refresh(race)
    return race


@router.put("/{race_id}", response_model=RaceAdminOut)
async def update_race(race_id: int, payload: RaceUpdate, db: AsyncSession = Depends(get_db)):
    race = await _get_race_or_404(db, race_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(race, key, value)
    db.add(race)
    await db.commit()
    await db.refresh(race)
    return race


@router.post("/{race_id}/toggle-active", response_model=RaceAdminOut)
async def toggle_race_active(race_id: int, db: AsyncSession = Depends(get_db)):
    race = await _get_race_or_404(db, race_id)
    race.is_active = not race.is_active
    db.add(race)
    await db.commit()
    await db.refresh(race)
    return race
