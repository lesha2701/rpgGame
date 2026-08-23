from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.boss_phase import BossPhase
from app.models.campaign_node import CampaignNode
from app.models.campaign_node_edge import CampaignNodeEdge
from app.models.campaign_region import CampaignRegion
from app.models.character_class import CharacterClass
from app.models.chest import Chest, ChestRarityProbability
from app.models.enemy_ability import EnemyAbility
from app.models.enemy_resistance import EnemyResistance
from app.models.enemy_template import EnemyTemplate
from app.models.enums import (
    CampaignNodeType,
    EquipmentSlot,
    ItemEffectTrigger,
    ItemEffectType,
    ItemStatType,
    QuestConditionType,
    Rarity,
    SkillType,
)
from app.models.expedition_template import ExpeditionTemplate
from app.models.hero_template import HeroTemplate
from app.models.item_affix import ItemAffix
from app.models.item_effect import ItemEffect
from app.models.item_template import ItemTemplate
from app.models.quest_definition import QuestDefinition
from app.models.race import Race
from app.models.skill_definition import SkillDefinition
from app.models.user import User
from app.models.user_hero import UserHero
from app.models.user_item import UserItem

DEFAULT_CLASS_STATS = dict(
    base_hp=100,
    base_attack=10,
    base_defense=10,
    base_speed=10,
    base_crit_chance=0.05,
    base_crit_damage=1.5,
    hp_per_level=5,
    attack_per_level=1,
    defense_per_level=1,
    speed_per_level=0.5,
)


async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> User:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one()


async def create_race(db: AsyncSession, code: str = "human", name: str = "Человек") -> Race:
    race = Race(code=code, name=name)
    db.add(race)
    await db.flush()
    return race


async def create_class(db: AsyncSession, code: str = "warrior", name: str = "Воин", **overrides) -> CharacterClass:
    data = {**DEFAULT_CLASS_STATS, **overrides}
    char_class = CharacterClass(code=code, name=name, **data)
    db.add(char_class)
    await db.flush()
    return char_class


async def create_hero_template(
    db: AsyncSession, name: str = "Тест-герой", race: Race | None = None, char_class: CharacterClass | None = None
) -> HeroTemplate:
    resolved_race = race if race is not None else await create_race(db)
    resolved_class = char_class if char_class is not None else await create_class(db)
    template = HeroTemplate(name=name, race_id=resolved_race.id, class_id=resolved_class.id)
    db.add(template)
    await db.flush()
    return template


async def create_skill_definition(
    db: AsyncSession,
    char_class: CharacterClass,
    code: str = "test_skill",
    name: str = "Тест-навык",
    required_hero_level: int = 1,
    skill_type: SkillType = SkillType.damage,
    base_power: float = 10,
    power_per_skill_level: float = 2,
    cooldown_turns: int = 2,
    **overrides,
) -> SkillDefinition:
    skill = SkillDefinition(
        class_id=char_class.id,
        code=code,
        name=name,
        required_hero_level=required_hero_level,
        skill_type=skill_type,
        base_power=base_power,
        power_per_skill_level=power_per_skill_level,
        cooldown_turns=cooldown_turns,
        **overrides,
    )
    db.add(skill)
    await db.flush()
    return skill


async def set_hero_level(db: AsyncSession, hero_id: int, level: int) -> None:
    hero = await db.get(UserHero, hero_id)
    assert hero is not None
    hero.level = level
    db.add(hero)
    await db.flush()


async def create_item_template(
    db: AsyncSession,
    slot: EquipmentSlot = EquipmentSlot.weapon,
    tier: int = 1,
    rarity: Rarity = Rarity.common,
    name: str | None = None,
    affix_stat_types: list[ItemStatType] | None = None,
) -> ItemTemplate:
    template = ItemTemplate(
        slot=slot, tier=tier, rarity=rarity, name=name or f"Тест-предмет T{tier} {rarity.value}"
    )
    db.add(template)
    await db.flush()
    for stat_type in affix_stat_types or []:
        db.add(ItemAffix(item_template_id=template.id, stat_type=stat_type))
    await db.flush()
    return template


async def grant_item_to_user(db: AsyncSession, user: User, template: ItemTemplate) -> UserItem:
    item = UserItem(owner_user_id=user.id, item_template_id=template.id, slot=template.slot)
    db.add(item)
    await db.flush()
    return item


async def set_balance(db: AsyncSession, user: User, amount: int) -> None:
    user.balance = amount
    db.add(user)
    await db.flush()


async def create_enemy_template(
    db: AsyncSession,
    name: str = "Тест-враг",
    level: int = 1,
    hp: int = 50,
    attack: int = 10,
    defense: int = 5,
    speed: int = 5,
    crit_chance: float = 0.0,
    crit_damage: float = 1.5,
    reward_xp: int = 20,
    reward_coins: int = 10,
    is_active: bool = True,
    is_boss: bool = False,
    stun_immune: bool = False,
    behavior_pattern: list | None = None,
) -> EnemyTemplate:
    enemy = EnemyTemplate(
        name=name,
        level=level,
        hp=hp,
        attack=attack,
        defense=defense,
        speed=speed,
        crit_chance=crit_chance,
        crit_damage=crit_damage,
        reward_xp=reward_xp,
        reward_coins=reward_coins,
        is_active=is_active,
        is_boss=is_boss,
        stun_immune=stun_immune,
        behavior_pattern=behavior_pattern,
    )
    db.add(enemy)
    await db.flush()
    return enemy


async def create_enemy_ability(
    db: AsyncSession,
    enemy: EnemyTemplate,
    code: str,
    name: str = "Способность",
    skill_type: SkillType = SkillType.damage,
    power: float = 10,
    cooldown_turns: int = 0,
    buff_stat: str = "attack",
    status_label: str | None = None,
    is_active: bool = True,
) -> EnemyAbility:
    ability = EnemyAbility(
        enemy_template_id=enemy.id, code=code, name=name, skill_type=skill_type, power=power,
        cooldown_turns=cooldown_turns, buff_stat=buff_stat, status_label=status_label, is_active=is_active,
    )
    db.add(ability)
    await db.flush()
    return ability


async def create_enemy_resistance(db: AsyncSession, enemy: EnemyTemplate, status_label: str, multiplier: float) -> EnemyResistance:
    resistance = EnemyResistance(enemy_template_id=enemy.id, status_label=status_label, multiplier=multiplier)
    db.add(resistance)
    await db.flush()
    return resistance


async def create_boss_phase(
    db: AsyncSession,
    enemy: EnemyTemplate,
    phase_order: int,
    hp_threshold_pct: float,
    behavior_pattern: list | None = None,
    attack_multiplier: float = 1.0,
    defense_multiplier: float = 1.0,
    unlock_ability_code: str | None = None,
    transition_text: str | None = None,
) -> BossPhase:
    phase = BossPhase(
        enemy_template_id=enemy.id, phase_order=phase_order, hp_threshold_pct=hp_threshold_pct,
        behavior_pattern=behavior_pattern, attack_multiplier=attack_multiplier, defense_multiplier=defense_multiplier,
        unlock_ability_code=unlock_ability_code, transition_text=transition_text,
    )
    db.add(phase)
    await db.flush()
    return phase


async def create_item_effect(
    db: AsyncSession,
    item_template: ItemTemplate,
    trigger: ItemEffectTrigger,
    effect_type: ItemEffectType,
    status_label: str | None = None,
    magnitude: float = 0,
    duration_turns: int | None = None,
) -> ItemEffect:
    effect = ItemEffect(
        item_template_id=item_template.id, trigger=trigger, effect_type=effect_type,
        status_label=status_label, magnitude=magnitude, duration_turns=duration_turns,
    )
    db.add(effect)
    await db.flush()
    return effect


async def create_campaign_region(db: AsyncSession, code: str, name: str = "Тест-регион", sort_order: int = 1) -> CampaignRegion:
    region = CampaignRegion(code=code, name=name, sort_order=sort_order)
    db.add(region)
    await db.flush()
    return region


async def create_campaign_node(
    db: AsyncSession,
    region: CampaignRegion,
    code: str,
    name: str = "Тест-узел",
    node_type: CampaignNodeType = CampaignNodeType.battle,
    enemy: EnemyTemplate | None = None,
    level: int = 1,
    depth: int = 0,
    sort_order: int = 1,
    is_active: bool = True,
) -> CampaignNode:
    node = CampaignNode(
        region_id=region.id, code=code, name=name, node_type=node_type,
        enemy_template_id=enemy.id if enemy else None, level=level, depth=depth, sort_order=sort_order,
        is_active=is_active,
    )
    db.add(node)
    await db.flush()
    return node


async def create_campaign_node_edge(db: AsyncSession, from_node: CampaignNode, to_node: CampaignNode) -> CampaignNodeEdge:
    edge = CampaignNodeEdge(from_node_id=from_node.id, to_node_id=to_node.id)
    db.add(edge)
    await db.flush()
    return edge


async def create_expedition_template(
    db: AsyncSession,
    name: str = "Тест-экспедиция",
    duration_seconds: int = 300,
    required_hero_level: int = 1,
    reward_xp: int = 20,
    reward_coins: int = 10,
    is_active: bool = True,
) -> ExpeditionTemplate:
    expedition = ExpeditionTemplate(
        name=name,
        duration_seconds=duration_seconds,
        required_hero_level=required_hero_level,
        reward_xp=reward_xp,
        reward_coins=reward_coins,
        is_active=is_active,
    )
    db.add(expedition)
    await db.flush()
    return expedition


async def create_quest_definition(
    db: AsyncSession,
    code: str = "test-quest",
    name: str = "Тест-квест",
    condition_type: QuestConditionType = QuestConditionType.battles_won,
    target_value: int = 1,
    reward_xp: int = 20,
    reward_coins: int = 10,
    is_active: bool = True,
) -> QuestDefinition:
    quest = QuestDefinition(
        code=code,
        name=name,
        condition_type=condition_type,
        target_value=target_value,
        reward_xp=reward_xp,
        reward_coins=reward_coins,
        is_active=is_active,
    )
    db.add(quest)
    await db.flush()
    return quest


async def create_chest(
    db: AsyncSession,
    price: int = 100,
    slug: str | None = None,
    guaranteed_min_rarity: Rarity | None = None,
    rarity_probabilities: dict[Rarity, float] | None = None,
    is_active: bool = True,
) -> Chest:
    probabilities = rarity_probabilities or {
        Rarity.common: 0.60,
        Rarity.rare: 0.25,
        Rarity.epic: 0.12,
        Rarity.legendary: 0.03,
    }
    chest = Chest(
        slug=slug or f"test-chest-{id(object())}",
        name="Тест-сундук",
        price=price,
        guaranteed_min_rarity=guaranteed_min_rarity,
        is_active=is_active,
    )
    db.add(chest)
    await db.flush()
    for rarity, probability in probabilities.items():
        db.add(ChestRarityProbability(chest_id=chest.id, rarity=rarity, probability=probability))
    await db.flush()
    return chest
