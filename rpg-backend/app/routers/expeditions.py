from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.user import User
from app.schemas.expedition import ExpeditionTemplateOut, UserExpeditionOut
from app.services.expedition_service import (
    claim_expedition,
    get_current_expedition,
    list_history,
    list_templates,
    start_expedition,
    template_to_out,
)
from app.services.hero_service import get_active_hero

# Two routers, two prefixes, one feature: `router` covers everything under
# /expeditions, `hero_router` covers the one hero-scoped read
# (GET /heroes/me/expedition) — mirrors how skills/inventory each get their
# own router mounted at a /heroes/me/* prefix rather than editing heroes.py
# directly (see app/main.py).
router = APIRouter()
hero_router = APIRouter()


async def _require_active_hero(db: AsyncSession, user: User):
    hero = await get_active_hero(db, user)
    if hero is None:
        raise NotFoundError("You don't have a hero yet")
    return hero


async def _hero_level_or_none(db: AsyncSession, user: User) -> int | None:
    hero = await get_active_hero(db, user)
    return hero.level if hero else None


@router.get("", response_model=list[ExpeditionTemplateOut])
async def list_expeditions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero_level = await _hero_level_or_none(db, user)
    templates = await list_templates(db)
    return [template_to_out(t, hero_level) for t in templates]


@router.get("/history", response_model=list[UserExpeditionOut])
async def expedition_history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await _require_active_hero(db, user)
    return await list_history(db, hero, user)


@router.get("/{expedition_template_id}", response_model=ExpeditionTemplateOut)
async def get_expedition(
    expedition_template_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    hero_level = await _hero_level_or_none(db, user)
    templates = await list_templates(db)
    template = next((t for t in templates if t.id == expedition_template_id), None)
    if template is None:
        raise NotFoundError("Expedition not found")
    return template_to_out(template, hero_level)


@router.post("/{expedition_template_id}/start", response_model=UserExpeditionOut, status_code=201)
async def start_expedition_endpoint(
    expedition_template_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    hero = await _require_active_hero(db, user)
    return await start_expedition(db, user, hero, expedition_template_id)


@router.post("/{user_expedition_id}/claim", response_model=UserExpeditionOut)
async def claim_expedition_endpoint(
    user_expedition_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    hero = await _require_active_hero(db, user)
    return await claim_expedition(db, user, hero, user_expedition_id)


@hero_router.get("/expedition", response_model=UserExpeditionOut | None)
async def my_current_expedition(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await _require_active_hero(db, user)
    return await get_current_expedition(db, hero, user)
