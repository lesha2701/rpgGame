from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.user import User
from app.schemas.campaign import CampaignActionRequest, CampaignBattleOut, CampaignMapOut, StartCampaignBattleRequest
from app.services.campaign_battle_service import get_campaign_battle, start_campaign_battle, submit_campaign_action
from app.services.campaign_service import get_campaign_map
from app.services.hero_service import get_active_hero

router = APIRouter()


async def _require_active_hero(db: AsyncSession, user: User):
    hero = await get_active_hero(db, user)
    if hero is None:
        raise NotFoundError("You don't have a hero yet")
    return hero


@router.get("/map", response_model=CampaignMapOut)
async def get_campaign_map_endpoint(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await get_campaign_map(db, user.id)


@router.post("/battles", response_model=CampaignBattleOut, status_code=201)
async def start_campaign_battle_endpoint(
    payload: StartCampaignBattleRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    hero = await _require_active_hero(db, user)
    return await start_campaign_battle(db, user, hero, payload.node_id)


@router.get("/battles/{campaign_battle_id}", response_model=CampaignBattleOut)
async def get_campaign_battle_endpoint(
    campaign_battle_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await get_campaign_battle(db, user, campaign_battle_id)


@router.post("/battles/{campaign_battle_id}/action", response_model=CampaignBattleOut)
async def submit_campaign_action_endpoint(
    campaign_battle_id: int,
    payload: CampaignActionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    hero = await _require_active_hero(db, user)
    return await submit_campaign_action(
        db, user, hero, campaign_battle_id, payload.round, payload.action_type, payload.skill_id
    )
