from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, InsufficientResourcesError, NotFoundError
from app.models.character_skill import CharacterSkill
from app.models.skill_definition import SkillDefinition
from app.models.user_hero import UserHero
from app.schemas.skill import (
    AvailableSkillOut,
    AvailableSkillsOut,
    CharacterSkillOut,
    SkillBudgetOut,
    SkillDefinitionOut,
)
from app.services.hero_service import lock_hero_for_update
from app.services.skill_progression import MAX_SKILL_LEVEL, power_at_level, total_skill_budget, upgrade_cost


async def _fetch_character_skill(db: AsyncSession, hero_id: int, skill_definition_id: int) -> CharacterSkill | None:
    result = await db.execute(
        select(CharacterSkill).where(
            CharacterSkill.hero_id == hero_id, CharacterSkill.skill_definition_id == skill_definition_id
        )
    )
    return result.scalar_one_or_none()


async def _spent_skill_points(db: AsyncSession, hero_id: int) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(CharacterSkill.level), 0)).where(CharacterSkill.hero_id == hero_id)
    )
    return int(result.scalar_one())


async def get_hero_skills(db: AsyncSession, hero_id: int) -> list[CharacterSkill]:
    result = await db.execute(
        select(CharacterSkill).where(CharacterSkill.hero_id == hero_id).order_by(CharacterSkill.id)
    )
    return list(result.scalars().all())


async def get_class_skill_definitions(db: AsyncSession, class_id: int) -> list[SkillDefinition]:
    result = await db.execute(
        select(SkillDefinition)
        .where(SkillDefinition.class_id == class_id, SkillDefinition.is_active.is_(True))
        .order_by(SkillDefinition.sort_order, SkillDefinition.id)
    )
    return list(result.scalars().all())


async def upgrade_skill(db: AsyncSession, hero_id: int, skill_definition_id: int) -> CharacterSkill:
    """Learns the skill (creates its CharacterSkill row at level 1) if the
    hero doesn't have it yet, or raises its level by 1 otherwise. Locks the
    hero row — not just the skill row — because the skill-point budget this
    checks against is shared across every skill the hero owns, so two
    concurrent upgrades of *different* skills on the same hero must still
    serialize against each other."""
    locked_hero = await lock_hero_for_update(db, hero_id)

    skill_def = await db.get(SkillDefinition, skill_definition_id)
    if skill_def is None or not skill_def.is_active or skill_def.class_id != locked_hero.hero_template.class_id:
        raise NotFoundError("Skill not found for this hero's class")

    if locked_hero.level < skill_def.required_hero_level:
        raise ConflictError(
            "Hero level too low to unlock this skill",
            details={"hero_level": locked_hero.level, "required_hero_level": skill_def.required_hero_level},
        )

    existing = await _fetch_character_skill(db, hero_id, skill_definition_id)
    current_level = existing.level if existing is not None else 0

    if current_level >= MAX_SKILL_LEVEL:
        raise ConflictError("Skill is already at max level", details={"max_level": MAX_SKILL_LEVEL})

    cost = upgrade_cost(current_level)
    spent = await _spent_skill_points(db, hero_id)
    budget = total_skill_budget(locked_hero.level)
    available = budget - spent
    if available < cost:
        raise InsufficientResourcesError(
            "Not enough skill points",
            details={"available": available, "required": cost, "budget": budget, "spent": spent},
        )

    if existing is None:
        skill = CharacterSkill(hero_id=hero_id, skill_definition_id=skill_definition_id, level=1)
        db.add(skill)
    else:
        existing.level = current_level + 1
        db.add(existing)
        skill = existing

    await db.commit()
    await db.refresh(skill)
    return skill


async def get_skill_budget(db: AsyncSession, hero: UserHero) -> tuple[int, int]:
    """Returns (total, spent) — available is total - spent."""
    spent = await _spent_skill_points(db, hero.id)
    total = total_skill_budget(hero.level)
    return total, spent


def character_skill_to_out(skill: CharacterSkill) -> CharacterSkillOut:
    return CharacterSkillOut(
        id=skill.id,
        level=skill.level,
        power=power_at_level(skill.skill_definition, skill.level),
        skill_definition=SkillDefinitionOut.model_validate(skill.skill_definition),
    )


async def get_available_skills_out(db: AsyncSession, hero: UserHero) -> AvailableSkillsOut:
    definitions = await get_class_skill_definitions(db, hero.hero_template.class_id)
    owned = await get_hero_skills(db, hero.id)
    owned_by_definition_id = {s.skill_definition_id: s for s in owned}
    total, spent = await get_skill_budget(db, hero)

    skills_out = []
    for definition in definitions:
        owned_skill = owned_by_definition_id.get(definition.id)
        current_level = owned_skill.level if owned_skill is not None else 0
        is_max = current_level >= MAX_SKILL_LEVEL
        skills_out.append(
            AvailableSkillOut(
                skill_definition=SkillDefinitionOut.model_validate(definition),
                is_unlocked=hero.level >= definition.required_hero_level,
                current_level=current_level,
                is_max_level=is_max,
                next_upgrade_cost=None if is_max else upgrade_cost(current_level),
            )
        )
    return AvailableSkillsOut(
        budget=SkillBudgetOut(total=total, spent=spent, available=total - spent), skills=skills_out
    )
