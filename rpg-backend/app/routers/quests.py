from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.user import User
from app.schemas.quest import QuestClaimOut, QuestOut
from app.services.hero_service import get_active_hero
from app.services.quest_service import claim_quest, list_quests

router = APIRouter()


@router.get("", response_model=list[QuestOut])
async def list_quests_endpoint(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # No active-hero requirement here on purpose: hero-scoped condition
    # types (hero_level/items_equipped/skills_upgraded) degrade to progress
    # 0 without one (quest_progression.get_quest_progress), so a
    # brand-new user can still see what's achievable before creating a hero.
    hero = await get_active_hero(db, user)
    return await list_quests(db, user, hero)


@router.post("/{user_quest_id}/claim", response_model=QuestClaimOut)
async def claim_quest_endpoint(
    user_quest_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    # Claiming always requires a hero: the reward includes XP, which has
    # nowhere to go without one.
    hero = await get_active_hero(db, user)
    if hero is None:
        raise NotFoundError("You don't have a hero yet")
    return await claim_quest(db, user, hero, user_quest_id)
