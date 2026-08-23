from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.minigame import (
    AlchemyStartOut,
    AlchemySubmitRequest,
    CupsGuessRequest,
    CupsRoundOut,
    DiceRoundOut,
    DummyCompleteRequest,
    DummyStartOut,
    MemorySubmitRequest,
    MemoryStartOut,
    MinigameResultOut,
    PairsCompleteRequest,
    PairsStartOut,
)
from app.services import minigame_service
from app.services.hero_service import get_active_hero

router = APIRouter()


@router.post("/memory/start", response_model=MemoryStartOut)
async def start_memory_game(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await get_active_hero(db, user)
    return await minigame_service.start_memory(db, user, hero)


@router.post("/memory/{attempt_id}/submit", response_model=MinigameResultOut)
async def submit_memory_game(
    attempt_id: int,
    payload: MemorySubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    hero = await get_active_hero(db, user)
    return await minigame_service.submit_memory(db, user, hero, attempt_id, payload.answer)


@router.post("/pairs/start", response_model=PairsStartOut)
async def start_pairs_game(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await get_active_hero(db, user)
    return await minigame_service.start_pairs(db, user, hero)


@router.post("/pairs/{attempt_id}/complete", response_model=MinigameResultOut)
async def complete_pairs_game(
    attempt_id: int,
    payload: PairsCompleteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    hero = await get_active_hero(db, user)
    return await minigame_service.complete_pairs(db, user, hero, attempt_id, payload.moves)


@router.post("/dummy/start", response_model=DummyStartOut)
async def start_dummy_game(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await get_active_hero(db, user)
    return await minigame_service.start_dummy(db, user, hero)


@router.post("/dummy/{attempt_id}/complete", response_model=MinigameResultOut)
async def complete_dummy_game(
    attempt_id: int,
    payload: DummyCompleteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    hero = await get_active_hero(db, user)
    return await minigame_service.complete_dummy(db, user, hero, attempt_id, payload.hits)


@router.post("/alchemy/start", response_model=AlchemyStartOut)
async def start_alchemy_game(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await get_active_hero(db, user)
    return await minigame_service.start_alchemy(db, user, hero)


@router.post("/alchemy/{attempt_id}/submit", response_model=MinigameResultOut)
async def submit_alchemy_game(
    attempt_id: int,
    payload: AlchemySubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    hero = await get_active_hero(db, user)
    return await minigame_service.submit_alchemy(db, user, hero, attempt_id, payload.answer)


@router.post("/dice/start", response_model=DiceRoundOut)
async def start_dice_game(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await get_active_hero(db, user)
    return await minigame_service.start_dice(db, user, hero)


@router.post("/dice/{attempt_id}/roll", response_model=DiceRoundOut)
async def roll_dice_game(
    attempt_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    hero = await get_active_hero(db, user)
    return await minigame_service.roll_dice(db, user, hero, attempt_id)


@router.post("/dice/{attempt_id}/bank", response_model=DiceRoundOut)
async def bank_dice_game(
    attempt_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    hero = await get_active_hero(db, user)
    return await minigame_service.bank_dice(db, user, hero, attempt_id)


@router.post("/cups/start", response_model=CupsRoundOut)
async def start_cups_game(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hero = await get_active_hero(db, user)
    return await minigame_service.start_cups(db, user, hero)


@router.post("/cups/{attempt_id}/guess", response_model=CupsRoundOut)
async def guess_cups_game(
    attempt_id: int,
    payload: CupsGuessRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    hero = await get_active_hero(db, user)
    return await minigame_service.guess_cups(db, user, hero, attempt_id, payload.cup)
