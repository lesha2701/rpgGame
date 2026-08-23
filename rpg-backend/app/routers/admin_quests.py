from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin
from app.core.exceptions import NotFoundError
from app.database import get_db
from app.models.quest_definition import QuestDefinition
from app.schemas.admin import QuestDefinitionAdminOut, QuestDefinitionCreate, QuestDefinitionUpdate

router = APIRouter(dependencies=[Depends(get_current_admin)])


async def _get_quest_or_404(db: AsyncSession, quest_id: int) -> QuestDefinition:
    result = await db.execute(select(QuestDefinition).where(QuestDefinition.id == quest_id))
    quest = result.scalar_one_or_none()
    if quest is None:
        raise NotFoundError("Quest definition not found")
    return quest


@router.get("", response_model=list[QuestDefinitionAdminOut])
async def list_all_quests(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(QuestDefinition).order_by(QuestDefinition.sort_order, QuestDefinition.id))
    return result.scalars().all()


@router.post("", response_model=QuestDefinitionAdminOut)
async def create_quest(payload: QuestDefinitionCreate, db: AsyncSession = Depends(get_db)):
    quest = QuestDefinition(**payload.model_dump())
    db.add(quest)
    await db.commit()
    await db.refresh(quest)
    return quest


@router.put("/{quest_id}", response_model=QuestDefinitionAdminOut)
async def update_quest(quest_id: int, payload: QuestDefinitionUpdate, db: AsyncSession = Depends(get_db)):
    quest = await _get_quest_or_404(db, quest_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(quest, key, value)
    db.add(quest)
    await db.commit()
    await db.refresh(quest)
    return quest


@router.post("/{quest_id}/toggle-active", response_model=QuestDefinitionAdminOut)
async def toggle_quest_active(quest_id: int, db: AsyncSession = Depends(get_db)):
    quest = await _get_quest_or_404(db, quest_id)
    quest.is_active = not quest.is_active
    db.add(quest)
    await db.commit()
    await db.refresh(quest)
    return quest
