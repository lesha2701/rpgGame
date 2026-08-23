"""Idempotent RPG catalog seed — every entity is looked up by a natural key
before being created, so running this twice never creates duplicates. Same
convention as the football app's app/seed.py.

    python -m app.seed
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.app_icon import AppIcon
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
from app.services.free_chest_service import FREE_CHEST_SLUG

RACES = [
    dict(code="human", name="Человек", sort_order=1),
    dict(code="orc", name="Орк", sort_order=2),
]

# Illustrative V1 balance numbers, not final tuning — expect these to move
# once real PvE/PvP data exists (Stage 8+). hp/attack/defense/speed_per_level
# are flat per-level growth added on top of the base_* columns.
CLASSES = [
    dict(
        code="warrior",
        name="Воин",
        sort_order=1,
        base_hp=120,
        base_attack=12,
        base_defense=10,
        base_speed=8,
        base_crit_chance=0.05,
        base_crit_damage=1.5,
        hp_per_level=8,
        attack_per_level=1.5,
        defense_per_level=1.2,
        speed_per_level=0.3,
    ),
    dict(
        code="archer",
        name="Лучник",
        sort_order=2,
        base_hp=90,
        base_attack=14,
        base_defense=6,
        base_speed=12,
        base_crit_chance=0.12,
        base_crit_damage=1.7,
        hp_per_level=5,
        attack_per_level=2.0,
        defense_per_level=0.6,
        speed_per_level=0.8,
    ),
    dict(
        code="mage",
        name="Маг",
        sort_order=3,
        base_hp=75,
        base_attack=16,
        base_defense=5,
        base_speed=9,
        base_crit_chance=0.08,
        base_crit_damage=1.8,
        hp_per_level=4,
        attack_per_level=2.2,
        defense_per_level=0.5,
        speed_per_level=0.5,
    ),
    dict(
        code="rogue",
        name="Разбойник",
        sort_order=4,
        base_hp=80,
        base_attack=13,
        base_defense=6,
        base_speed=14,
        base_crit_chance=0.18,
        base_crit_damage=2.0,
        hp_per_level=4.5,
        attack_per_level=1.8,
        defense_per_level=0.5,
        speed_per_level=1.0,
    ),
]

# 3 skills per class, unlocking in a staggered sequence (level 1 / 5 / 15)
# per Stage 3's requirement — the first is available from the start, the
# second and third gate progressively later. base_power/power_per_skill_level
# are illustrative future-battle-engine inputs, not applied to anything yet.
SKILLS = {
    "warrior": [
        dict(
            code="power_strike", name="Мощный удар", sort_order=1, required_hero_level=1,
            skill_type=SkillType.damage, base_power=20, power_per_skill_level=4, cooldown_turns=2,
            description="Сильный удар оружием по одной цели.",
        ),
        dict(
            code="shield_wall", name="Стена щитов", sort_order=2, required_hero_level=5,
            skill_type=SkillType.shield, base_power=15, power_per_skill_level=3, cooldown_turns=4,
            description="Временно поглощает часть входящего урона.",
        ),
        dict(
            code="bleeding_cut", name="Кровавый надрез", sort_order=3, required_hero_level=15,
            skill_type=SkillType.dot, base_power=6, power_per_skill_level=1.5, cooldown_turns=3,
            description="Наносит урон от кровотечения в течение нескольких ходов.",
        ),
    ],
    "archer": [
        dict(
            code="aimed_shot", name="Меткий выстрел", sort_order=1, required_hero_level=1,
            skill_type=SkillType.damage, base_power=22, power_per_skill_level=4.5, cooldown_turns=2,
            description="Точный выстрел с повышенным уроном.",
        ),
        dict(
            code="arrow_rain", name="Град стрел", sort_order=2, required_hero_level=5,
            skill_type=SkillType.damage, base_power=16, power_per_skill_level=3, cooldown_turns=4,
            description="Серия стрел, наносящих урон.",
        ),
        dict(
            code="binding_trap", name="Ловушка", sort_order=3, required_hero_level=15,
            skill_type=SkillType.stun, base_power=1, power_per_skill_level=0, cooldown_turns=5,
            # Stage 13: also flagged as an Interrupt — cancels a queued
            # campaign-boss action even through stun_immune, unlike a
            # plain stun (see battle_engine.py's is_interrupt docstring).
            is_interrupt=True,
            description="Обездвиживает противника на короткое время, срывая его текущее действие.",
        ),
    ],
    "mage": [
        dict(
            code="fireball", name="Огненный шар", sort_order=1, required_hero_level=1,
            skill_type=SkillType.damage, base_power=24, power_per_skill_level=5, cooldown_turns=2,
            description="Огненный снаряд, наносящий урон цели.",
        ),
        dict(
            code="arcane_shield", name="Арканный щит", sort_order=2, required_hero_level=5,
            skill_type=SkillType.shield, base_power=18, power_per_skill_level=3.5, cooldown_turns=4,
            description="Магический барьер, поглощающий урон.",
        ),
        dict(
            code="meteor", name="Метеор", sort_order=3, required_hero_level=15,
            skill_type=SkillType.damage, base_power=35, power_per_skill_level=7, cooldown_turns=6,
            description="Мощный удар по площади с высоким уроном.",
        ),
    ],
    "rogue": [
        dict(
            code="backstab", name="Удар в спину", sort_order=1, required_hero_level=1,
            skill_type=SkillType.damage, base_power=21, power_per_skill_level=4.5, cooldown_turns=2,
            description="Быстрый удар с высоким шансом критического урона.",
        ),
        dict(
            code="smoke_screen", name="Дымовая завеса", sort_order=2, required_hero_level=5,
            skill_type=SkillType.buff, base_power=10, power_per_skill_level=2, cooldown_turns=4,
            description="Временно повышает уклонение.",
        ),
        dict(
            code="poison_blade", name="Отравленный клинок", sort_order=3, required_hero_level=15,
            skill_type=SkillType.dot, base_power=7, power_per_skill_level=1.5, cooldown_turns=3,
            description="Наносит урон от яда в течение нескольких ходов.",
        ),
    ],
}

# Item catalog: systematic Tier x Slot x Rarity generation (10 x 7 x 4 = 280
# templates) — every tier has items in every slot at every rarity, so any
# tier's chest can always draw from every slot, not just Weapon. Stat
# numbers are never seeded here — they're always computed from
# (slot, tier, rarity) by services/item_progression.py. Names come from
# ITEM_NAMES_RU below (a pure function of slot+tier — see its own
# docstring); art (image_path) is admin-uploaded, not seeded here.
ALL_SLOTS = (
    EquipmentSlot.weapon,
    EquipmentSlot.helmet,
    EquipmentSlot.armor,
    EquipmentSlot.boots,
    EquipmentSlot.gloves,
    EquipmentSlot.ring,
    EquipmentSlot.amulet,
)
ALL_RARITIES = (Rarity.common, Rarity.rare, Rarity.epic, Rarity.legendary)

# Deterministic per-rarity affix stat types — count must match
# item_progression.RARITY_AFFIX_COUNT (Common=0, Rare=1, Epic=2, Legendary=3).
RARITY_AFFIX_STATS = {
    Rarity.common: [],
    Rarity.rare: [ItemStatType.hp],
    Rarity.epic: [ItemStatType.hp, ItemStatType.speed],
    Rarity.legendary: [ItemStatType.hp, ItemStatType.speed, ItemStatType.defense],
}

# Name is a pure function of (slot, tier) — rarity is deliberately NOT part
# of it. Rarity already has its own color/label treatment on the card
# (RARITY_TEXT_CLASS/RARITY_LABEL, frontend), and tier already has its own
# "T{n}" badge — folding both into the name too ("Меч 5 тира (редкий)")
# was redundant with what the card already shows. One escalating name per
# (slot, tier) instead: tiers 1-3 vary material/craft, tiers 4-10 share a
# prestige-word ladder (страж → ветеран → рыцарский → чемпион → герой →
# легенда → владыка) applied per slot, so a higher tier always reads as
# grander regardless of which rarity roll it happens to be.
ITEM_NAMES_RU: dict[EquipmentSlot, dict[int, str]] = {
    EquipmentSlot.weapon: {
        1: "Деревянный меч", 2: "Кованый меч", 3: "Стальной клинок", 4: "Клинок стража",
        5: "Меч ветерана", 6: "Рыцарский меч", 7: "Меч чемпиона", 8: "Клинок героя",
        9: "Клинок легенды", 10: "Меч владыки",
    },
    EquipmentSlot.helmet: {
        1: "Кожаный шлем", 2: "Клёпаный шлем", 3: "Стальной шлем", 4: "Шлем стража",
        5: "Шлем ветерана", 6: "Рыцарский шлем", 7: "Шлем чемпиона", 8: "Венец героя",
        9: "Шлем легенды", 10: "Корона владыки",
    },
    EquipmentSlot.armor: {
        1: "Стёганый доспех", 2: "Кожаный доспех", 3: "Кольчуга", 4: "Доспех стража",
        5: "Доспех ветерана", 6: "Рыцарские латы", 7: "Латы чемпиона", 8: "Доспех героя",
        9: "Доспех легенды", 10: "Латы владыки",
    },
    EquipmentSlot.boots: {
        1: "Изношенные сапоги", 2: "Дорожные сапоги", 3: "Кожаные сапоги", 4: "Сапоги стража",
        5: "Сапоги ветерана", 6: "Рыцарские сапоги", 7: "Сапоги чемпиона", 8: "Сапоги героя",
        9: "Сапоги легенды", 10: "Сапоги владыки",
    },
    EquipmentSlot.gloves: {
        1: "Рваные перчатки", 2: "Кожаные перчатки", 3: "Клёпаные перчатки", 4: "Перчатки стража",
        5: "Перчатки ветерана", 6: "Рыцарские перчатки", 7: "Перчатки чемпиона", 8: "Перчатки героя",
        9: "Перчатки легенды", 10: "Перчатки владыки",
    },
    EquipmentSlot.ring: {
        1: "Медное кольцо", 2: "Бронзовое кольцо", 3: "Серебряное кольцо", 4: "Кольцо стража",
        5: "Кольцо ветерана", 6: "Рыцарское кольцо", 7: "Кольцо чемпиона", 8: "Кольцо героя",
        9: "Кольцо легенды", 10: "Кольцо владыки",
    },
    EquipmentSlot.amulet: {
        1: "Костяной амулет", 2: "Медный амулет", 3: "Резной амулет", 4: "Амулет стража",
        5: "Амулет ветерана", 6: "Рыцарский амулет", 7: "Амулет чемпиона", 8: "Амулет героя",
        9: "Амулет легенды", 10: "Амулет владыки",
    },
}


def _item_name(slot: EquipmentSlot, tier: int) -> str:
    return ITEM_NAMES_RU[slot][tier]


# Chests no longer belong to a fixed equipment Tier (removed — see Chest's
# docstring): a chest's reward tier is capped by the *opening hero's own*
# tier, not by the chest. Ten "quality" rungs still exist so there's a
# meaningful price ladder, but they now differ from each other only by
# price and rarity odds (mostly-common/cheap up to mostly-legendary/
# expensive) — illustrative and meant to be rebalanced via the admin API,
# not final tuning. Same interpolation formula as migration 0014's
# one-time data migration for pre-existing rows; kept in sync by hand
# since a migration must never import live app code.
CHEST_PRICES = {1: 100, 2: 250, 3: 500, 4: 900, 5: 1500, 6: 2500, 7: 4000, 8: 6500, 9: 10000, 10: 16000}
CHEST_NAMES = {
    1: "Простой сундук",
    2: "Крепкий сундук",
    3: "Добротный сундук",
    4: "Прочный сундук",
    5: "Ценный сундук",
    6: "Редкий сундук",
    7: "Изысканный сундук",
    8: "Роскошный сундук",
    9: "Королевский сундук",
    10: "Легендарный сундук",
}


def _chest_rarity_probabilities(quality: int) -> dict[Rarity, float]:
    t = (max(1, min(quality, 10)) - 1) / 9
    common = round(0.70 + (0.05 - 0.70) * t, 4)
    legendary = round(0.01 + (0.35 - 0.01) * t, 4)
    epic = round(0.07 + (0.30 - 0.07) * t, 4)
    rare = round(1.0 - common - epic - legendary, 4)
    return {Rarity.common: common, Rarity.rare: rare, Rarity.epic: epic, Rarity.legendary: legendary}


# Deliberately not all 8 race x class combinations (2 races x 4 classes) —
# Race and CharacterClass are independent catalogs; these four just
# demonstrate that independence without exhaustively generating every combo.
HERO_TEMPLATES = [
    dict(name="Алдрик", race="human", cls="warrior", sort_order=1, description="Человек-воин, стойкий и решительный."),
    dict(name="Кеш", race="orc", cls="archer", sort_order=2, description="Орк-лучник с острым глазом."),
    dict(name="Эландра", race="human", cls="mage", sort_order=3, description="Человек-маг, изучающая тайные искусства."),
    dict(name="Грикс", race="orc", cls="rogue", sort_order=4, description="Орк-разбойник, быстрый и безжалостный."),
]


# Illustrative V1 PvE balance, not final tuning — same caveat as CLASSES.
# `level` doubles as the required hero level to challenge the enemy (see
# EnemyTemplate docstring), so the sequence below is a soft difficulty ramp
# a fresh level-1 hero can walk through as they level up.
ENEMIES = [
    dict(
        name="Гоблин", sort_order=1, level=1, hp=60, attack=8, defense=4, speed=6,
        crit_chance=0.05, crit_damage=1.5, reward_xp=15, reward_coins=10,
        description="Мелкий, но верткий падальщик из приграничных лесов.",
    ),
    dict(
        name="Скелет", sort_order=2, level=3, hp=90, attack=11, defense=6, speed=7,
        crit_chance=0.05, crit_damage=1.5, reward_xp=25, reward_coins=20,
        description="Оживший воин из старого захоронения, лишенный страха боли.",
    ),
    dict(
        name="Орк-воин", sort_order=3, level=6, hp=150, attack=16, defense=10, speed=8,
        crit_chance=0.05, crit_damage=1.5, reward_xp=45, reward_coins=35,
        description="Ветеран орочьих набегов, закованный в грубые доспехи.",
    ),
    dict(
        name="Темный маг", sort_order=4, level=10, hp=130, attack=22, defense=8, speed=10,
        crit_chance=0.15, crit_damage=1.8, reward_xp=80, reward_coins=60,
        description="Отступник, торгующий запретными заклинаниями за силу.",
    ),
    dict(
        name="Элитный орк", sort_order=5, level=15, hp=220, attack=28, defense=16, speed=9,
        crit_chance=0.08, crit_damage=1.6, reward_xp=140, reward_coins=100,
        description="Предводитель орочьего отряда, закаленный в десятках битв.",
    ),
    # Stage 13 additions: enemies with a behavior_pattern (see
    # ENEMY_ABILITIES below) for the interactive Campaign — every enemy
    # above still has no abilities (behavior_pattern=None), so it keeps
    # Basic-Attack-only Stage 6 PvE behavior unchanged; is_boss/
    # stun_immune both default False, so they too are unaffected.
    dict(
        name="Лесной волк", sort_order=6, level=2, hp=65, attack=9, defense=3, speed=11,
        crit_chance=0.10, crit_damage=1.5, reward_xp=18, reward_coins=12,
        description="Быстрый хищник, нападающий стаей на одиноких путников.",
        behavior_pattern=["bleed_bite", "basic_attack", "basic_attack"],
    ),
    dict(
        name="Гоблин-шаман", sort_order=7, level=5, hp=100, attack=10, defense=5, speed=8,
        crit_chance=0.05, crit_damage=1.5, reward_xp=40, reward_coins=28,
        description="Слабеет врагов проклятиями прежде, чем те успевают приблизиться.",
        behavior_pattern=["weaken", "basic_attack", "basic_attack"],
    ),
    dict(
        name="Костяной страж", sort_order=8, level=8, hp=140, attack=13, defense=9, speed=6,
        crit_chance=0.05, crit_damage=1.5, reward_xp=55, reward_coins=40,
        description="Древний страж склепа, чередующий удары с магической защитой.",
        behavior_pattern=["basic_attack", "bone_shield", "basic_attack", "basic_attack"],
    ),
    dict(
        name="Вождь Оркхан", sort_order=9, level=20, hp=480, attack=24, defense=14, speed=9,
        crit_chance=0.10, crit_damage=1.6, reward_xp=250, reward_coins=180,
        description="Предводитель орочьих кланов предгорий — первый настоящий босс кампании.",
        is_boss=True, stun_immune=True,
        behavior_pattern=["basic_attack", "heavy_strike", "basic_attack", "warcry"],
    ),
    dict(
        name="Огненный элементаль", sort_order=10, level=28, hp=260, attack=22, defense=12, speed=10,
        crit_chance=0.05, crit_damage=1.5, reward_xp=140, reward_coins=100,
        description="Сгусток пламени из пепельных пустошей, обжигающий всё живое.",
        behavior_pattern=["ember_touch", "basic_attack", "basic_attack"],
    ),
    dict(
        name="Ледяной страж", sort_order=11, level=34, hp=320, attack=20, defense=20, speed=5,
        crit_chance=0.05, crit_damage=1.5, reward_xp=170, reward_coins=130,
        description="Элитный часовой ледяного хребта, укрывающийся за стеной льда.",
        behavior_pattern=["basic_attack", "frost_bite", "basic_attack", "ice_wall"],
    ),
    dict(
        name="Древний дракон Иглаз", sort_order=12, level=45, hp=900, attack=38, defense=22, speed=11,
        crit_chance=0.15, crit_damage=1.8, reward_xp=600, reward_coins=450,
        description="Хранитель разрушенных руин, страж среднего рубежа кампании.",
        is_boss=True, stun_immune=True,
        behavior_pattern=["basic_attack", "flame_breath", "basic_attack", "wing_buffet"],
    ),
    # Levels 1-100 density pass — more enemies per region (a bit more per
    # block, as requested) plus 3 new regions extending the campaign all
    # the way to a level-100 final boss. Plain "battle" trash mobs below
    # deliberately have no behavior_pattern (Basic Attack only, same as
    # every enemy since Stage 6) — full movesets/resistances/phases are
    # reserved for elites and bosses, matching the existing density.
    dict(
        name="Дикий кабан", sort_order=13, level=2, hp=68, attack=10, defense=3, speed=8,
        crit_chance=0.05, crit_damage=1.5, reward_xp=18, reward_coins=13,
        description="Раздражительный секач, атакующий всё, что движется у него на пути.",
    ),
    dict(
        name="Лесные разбойники", sort_order=14, level=10, hp=140, attack=19, defense=9, speed=9,
        crit_chance=0.08, crit_damage=1.5, reward_xp=70, reward_coins=50,
        description="Банда изгнанников, промышляющая грабежом на лесных тропах.",
    ),
    dict(
        name="Орочий разведчик", sort_order=15, level=8, hp=120, attack=15, defense=7, speed=11,
        crit_chance=0.08, crit_damage=1.5, reward_xp=48, reward_coins=34,
        description="Быстрый и осторожный дозорный орочьих кланов.",
    ),
    dict(
        name="Орочий жрец Гром", sort_order=16, level=18, hp=260, attack=26, defense=15, speed=9,
        crit_chance=0.08, crit_damage=1.6, reward_xp=190, reward_coins=140,
        description="Служитель тёмных духов, ослабляющий врагов проклятиями.",
        behavior_pattern=["curse", "basic_attack", "basic_attack"],
    ),
    dict(
        name="Пепельный тролль", sort_order=17, level=22, hp=280, attack=27, defense=16, speed=7,
        crit_chance=0.05, crit_damage=1.5, reward_xp=150, reward_coins=110,
        description="Тролль, обожжённый пеплом пустошей и не чувствующий боли.",
    ),
    dict(
        name="Огненная саламандра", sort_order=18, level=31, hp=300, attack=29, defense=14, speed=12,
        crit_chance=0.10, crit_damage=1.6, reward_xp=200, reward_coins=150,
        description="Проворная ящерица, живущая в жерлах пепельных пустошей.",
        behavior_pattern=["flame_lash", "basic_attack", "basic_attack"],
    ),
    dict(
        name="Лагерь пустошей", sort_order=19, level=36, hp=340, attack=30, defense=18, speed=8,
        crit_chance=0.05, crit_damage=1.5, reward_xp=230, reward_coins=170,
        description="Отряд закалённых пустошами наёмников на границе драконьих земель.",
    ),
    dict(
        name="Каменный голем", sort_order=20, level=42, hp=420, attack=32, defense=28, speed=4,
        crit_chance=0.02, crit_damage=1.4, reward_xp=280, reward_coins=200,
        description="Ожившая статуя, охраняющая обрушенные залы драконьих руин.",
        behavior_pattern=["basic_attack", "stone_slam", "basic_attack", "rock_armor"],
    ),
    dict(
        name="Утопленный страж", sort_order=21, level=52, hp=560, attack=40, defense=24, speed=8,
        crit_chance=0.05, crit_damage=1.5, reward_xp=340, reward_coins=250,
        description="Некогда воин, утонувший в затопленных склепах и вставший вновь.",
    ),
    dict(
        name="Болотная ведьма", sort_order=22, level=58, hp=600, attack=42, defense=20, speed=11,
        crit_chance=0.12, crit_damage=1.7, reward_xp=420, reward_coins=320,
        description="Отшельница катакомб, насылающая порчу на незваных гостей.",
        behavior_pattern=["hex", "basic_attack", "basic_attack"],
    ),
    dict(
        name="Легион костей", sort_order=23, level=58, hp=650, attack=44, defense=26, speed=9,
        crit_chance=0.05, crit_damage=1.5, reward_xp=420, reward_coins=320,
        description="Отряд оживших воинов, марширующий по затопленным коридорам.",
    ),
    dict(
        name="Хранитель оссуария", sort_order=24, level=64, hp=720, attack=46, defense=30, speed=8,
        crit_chance=0.08, crit_damage=1.6, reward_xp=520, reward_coins=390,
        description="Страж костехранилища, возводящий стены из костей павших.",
        behavior_pattern=["basic_attack", "bone_wall", "basic_attack", "basic_attack"],
    ),
    dict(
        name="Лич Морвейн", sort_order=25, level=70, hp=1400, attack=55, defense=30, speed=10,
        crit_chance=0.15, crit_damage=1.8, reward_xp=1100, reward_coins=800,
        description="Некромант, заточивший собственную смерть ради власти над катакомбами.",
        is_boss=True, stun_immune=True,
        behavior_pattern=["basic_attack", "death_bolt", "basic_attack", "soul_drain"],
    ),
    dict(
        name="Страж-часовой", sort_order=26, level=72, hp=900, attack=58, defense=34, speed=10,
        crit_chance=0.05, crit_damage=1.5, reward_xp=650, reward_coins=480,
        description="Древний конструкт, несущий стражу у подножия небесной цитадели.",
    ),
    dict(
        name="Буревая гарпия", sort_order=27, level=78, hp=950, attack=62, defense=28, speed=16,
        crit_chance=0.15, crit_damage=1.7, reward_xp=780, reward_coins=580,
        description="Хищница грозовых потоков, атакующая на огромной скорости.",
        behavior_pattern=["gale_strike", "basic_attack", "basic_attack"],
    ),
    dict(
        name="Железный голем", sort_order=28, level=78, hp=1100, attack=60, defense=44, speed=5,
        crit_chance=0.02, crit_damage=1.4, reward_xp=780, reward_coins=580,
        description="Тяжёлый страж кузни, выкованный для обороны цитадели.",
    ),
    dict(
        name="Страж врат Серафим", sort_order=29, level=84, hp=1200, attack=66, defense=38, speed=11,
        crit_chance=0.10, crit_damage=1.6, reward_xp=950, reward_coins=700,
        description="Последний страж перед троном архонта, вершащий кару и защиту разом.",
        behavior_pattern=["basic_attack", "judgment", "basic_attack", "radiant_shield"],
    ),
    dict(
        name="Архонт Забвения", sort_order=30, level=90, hp=2200, attack=75, defense=40, speed=12,
        crit_chance=0.15, crit_damage=1.8, reward_xp=1800, reward_coins=1300,
        description="Владыка небесной цитадели, стирающий врагов из самого времени.",
        is_boss=True, stun_immune=True,
        behavior_pattern=["basic_attack", "oblivion_wave", "basic_attack", "time_stop"],
    ),
    dict(
        name="Порождение Бездны", sort_order=31, level=92, hp=1600, attack=78, defense=42, speed=11,
        crit_chance=0.08, crit_damage=1.6, reward_xp=1500, reward_coins=1100,
        description="Существо, просочившееся сквозь разлом на границе миров.",
    ),
    dict(
        name="Рыцарь Бездны", sort_order=32, level=96, hp=1900, attack=85, defense=48, speed=10,
        crit_chance=0.12, crit_damage=1.7, reward_xp=1900, reward_coins=1400,
        description="Павший герой, поднявший клинок на службу Бездне.",
        behavior_pattern=["basic_attack", "abyss_cleave", "basic_attack", "dark_ward"],
    ),
    dict(
        name="Владыка Бездны Некрон", sort_order=33, level=100, hp=3500, attack=95, defense=50, speed=13,
        crit_chance=0.20, crit_damage=1.9, reward_xp=3000, reward_coins=2200,
        description="Финальный владыка Бездны — последнее испытание кампании.",
        is_boss=True, stun_immune=True,
        behavior_pattern=["basic_attack", "void_rend", "basic_attack", "abyssal_grasp"],
    ),
]

# One list of EnemyAbility rows per enemy name — structurally mirrors
# SKILLS' per-class layout above. Referenced by ENEMIES' behavior_pattern
# code strings.
ENEMY_ABILITIES: dict[str, list[dict]] = {
    "Лесной волк": [
        dict(code="bleed_bite", name="Кровавый укус", skill_type=SkillType.dot, power=5, cooldown_turns=2, status_label="bleed"),
    ],
    "Гоблин-шаман": [
        dict(code="weaken", name="Слабость", skill_type=SkillType.debuff, power=4, cooldown_turns=3, buff_stat="attack"),
    ],
    "Костяной страж": [
        dict(code="bone_shield", name="Костяной барьер", skill_type=SkillType.shield, power=25, cooldown_turns=4),
    ],
    "Орочий жрец Гром": [
        dict(code="curse", name="Проклятие", skill_type=SkillType.debuff, power=6, cooldown_turns=3, buff_stat="defense"),
    ],
    "Вождь Оркхан": [
        dict(code="heavy_strike", name="Сокрушительный удар", skill_type=SkillType.damage, power=34, cooldown_turns=3),
        dict(code="warcry", name="Боевой клич", skill_type=SkillType.buff, power=6, cooldown_turns=5, buff_stat="attack"),
    ],
    "Огненный элементаль": [
        dict(code="ember_touch", name="Тлеющее прикосновение", skill_type=SkillType.dot, power=9, cooldown_turns=2, status_label="burn"),
    ],
    "Огненная саламандра": [
        dict(code="flame_lash", name="Огненный хлыст", skill_type=SkillType.dot, power=10, cooldown_turns=2, status_label="burn"),
    ],
    "Каменный голем": [
        dict(code="stone_slam", name="Каменный удар", skill_type=SkillType.damage, power=45, cooldown_turns=3),
        dict(code="rock_armor", name="Каменная броня", skill_type=SkillType.shield, power=50, cooldown_turns=4),
    ],
    "Ледяной страж": [
        dict(code="frost_bite", name="Морозный укус", skill_type=SkillType.dot, power=7, cooldown_turns=2, status_label="frost"),
        dict(code="ice_wall", name="Ледяная стена", skill_type=SkillType.shield, power=40, cooldown_turns=5),
    ],
    "Древний дракон Иглаз": [
        dict(code="flame_breath", name="Огненное дыхание", skill_type=SkillType.damage, power=55, cooldown_turns=4),
        dict(code="wing_buffet", name="Удар крыла", skill_type=SkillType.stun, power=1, cooldown_turns=5),
    ],
    "Болотная ведьма": [
        dict(code="hex", name="Порча", skill_type=SkillType.debuff, power=8, cooldown_turns=3, buff_stat="attack"),
    ],
    "Хранитель оссуария": [
        dict(code="bone_wall", name="Костяная стена", skill_type=SkillType.shield, power=70, cooldown_turns=4),
    ],
    "Лич Морвейн": [
        dict(code="death_bolt", name="Смертельный луч", skill_type=SkillType.damage, power=80, cooldown_turns=3),
        dict(code="soul_drain", name="Похищение души", skill_type=SkillType.dot, power=15, cooldown_turns=3, status_label="poison"),
    ],
    "Буревая гарпия": [
        dict(code="gale_strike", name="Удар шторма", skill_type=SkillType.damage, power=95, cooldown_turns=3),
    ],
    "Страж врат Серафим": [
        dict(code="judgment", name="Кара", skill_type=SkillType.damage, power=110, cooldown_turns=4),
        dict(code="radiant_shield", name="Сияющий щит", skill_type=SkillType.shield, power=100, cooldown_turns=4),
    ],
    "Архонт Забвения": [
        dict(code="oblivion_wave", name="Волна забвения", skill_type=SkillType.damage, power=130, cooldown_turns=3),
        dict(code="time_stop", name="Остановка времени", skill_type=SkillType.stun, power=1, cooldown_turns=5),
    ],
    "Рыцарь Бездны": [
        dict(code="abyss_cleave", name="Раскол бездны", skill_type=SkillType.damage, power=150, cooldown_turns=3),
        dict(code="dark_ward", name="Тёмная защита", skill_type=SkillType.shield, power=130, cooldown_turns=4),
    ],
    "Владыка Бездны Некрон": [
        dict(code="void_rend", name="Разрыв пустоты", skill_type=SkillType.damage, power=170, cooldown_turns=3),
        dict(code="abyssal_grasp", name="Хватка бездны", skill_type=SkillType.stun, power=1, cooldown_turns=5),
    ],
}

# EnemyResistance rows — status_label multiplier (>1.0 vulnerable, <1.0
# resistant). Огненный элементаль resisting its own element while being
# vulnerable to Bleed is the canonical "know your enemy" example from the
# Stage 13 design report.
ENEMY_RESISTANCES: dict[str, list[dict]] = {
    "Огненный элементаль": [
        dict(status_label="burn", multiplier=0.2),
        dict(status_label="bleed", multiplier=1.3),
    ],
    "Огненная саламандра": [
        dict(status_label="burn", multiplier=0.3),
    ],
    "Лич Морвейн": [
        dict(status_label="bleed", multiplier=0.3),
        dict(status_label="burn", multiplier=1.4),
    ],
    "Архонт Забвения": [
        dict(status_label="frost", multiplier=0.5),
        dict(status_label="burn", multiplier=1.2),
    ],
    "Владыка Бездны Некрон": [
        dict(status_label="poison", multiplier=0.3),
        dict(status_label="burn", multiplier=0.7),
        dict(status_label="bleed", multiplier=1.3),
    ],
}

# BossPhase rows — phase_order=1 always covers 100% HP (the fight's
# starting state); later phases have progressively lower hp_threshold_pct
# and become active once the boss's HP% drops to/below that value (see
# campaign_battle_service._pick_phase). transition_text is shown to the
# player exactly once, as a combat log entry, the round the phase becomes
# active (Stage 13 spec §9).
BOSS_PHASES: dict[str, list[dict]] = {
    "Вождь Оркхан": [
        dict(phase_order=1, hp_threshold_pct=100),
        dict(
            phase_order=2, hp_threshold_pct=60, attack_multiplier=1.15,
            behavior_pattern=["heavy_strike", "basic_attack", "warcry", "heavy_strike"],
            unlock_ability_code="heavy_strike",
            transition_text="Оркхан входит в ярость! Его удары становятся быстрее и опаснее.",
        ),
        dict(
            phase_order=3, hp_threshold_pct=30, attack_multiplier=1.35, defense_multiplier=0.85,
            behavior_pattern=["heavy_strike", "heavy_strike", "basic_attack"],
            transition_text="Раненый Оркхан отбрасывает оборону и бьёт на пределе сил!",
        ),
    ],
    "Древний дракон Иглаз": [
        dict(phase_order=1, hp_threshold_pct=100),
        dict(
            phase_order=2, hp_threshold_pct=65, attack_multiplier=1.2,
            behavior_pattern=["flame_breath", "basic_attack", "wing_buffet", "flame_breath"],
            transition_text="Дракон вздымается в воздух — пламя разгорается ярче!",
        ),
        dict(
            phase_order=3, hp_threshold_pct=30, attack_multiplier=1.5, defense_multiplier=0.7,
            behavior_pattern=["flame_breath", "flame_breath", "wing_buffet"],
            unlock_ability_code="flame_breath",
            transition_text="Раненый дракон обрушивает всю свою ярость!",
        ),
    ],
    "Лич Морвейн": [
        dict(phase_order=1, hp_threshold_pct=100),
        dict(
            phase_order=2, hp_threshold_pct=60, attack_multiplier=1.2,
            behavior_pattern=["death_bolt", "basic_attack", "soul_drain", "death_bolt"],
            transition_text="Лич призывает души павших!",
        ),
        dict(
            phase_order=3, hp_threshold_pct=25, attack_multiplier=1.5, defense_multiplier=0.8,
            behavior_pattern=["death_bolt", "soul_drain", "death_bolt"],
            unlock_ability_code="soul_drain",
            transition_text="Морвейн раскрывает истинную мощь некромантии!",
        ),
    ],
    "Архонт Забвения": [
        dict(phase_order=1, hp_threshold_pct=100),
        dict(
            phase_order=2, hp_threshold_pct=55, attack_multiplier=1.25,
            behavior_pattern=["oblivion_wave", "basic_attack", "time_stop", "oblivion_wave"],
            transition_text="Архонт разрывает пространство вокруг себя!",
        ),
        dict(
            phase_order=3, hp_threshold_pct=25, attack_multiplier=1.5, defense_multiplier=0.75,
            behavior_pattern=["oblivion_wave", "time_stop", "oblivion_wave"],
            unlock_ability_code="time_stop",
            transition_text="Забвение поглощает поле боя!",
        ),
    ],
    "Владыка Бездны Некрон": [
        dict(phase_order=1, hp_threshold_pct=100),
        dict(
            phase_order=2, hp_threshold_pct=65, attack_multiplier=1.2,
            behavior_pattern=["void_rend", "basic_attack", "abyssal_grasp", "void_rend"],
            transition_text="Некрон разрывает завесу между мирами!",
        ),
        dict(
            phase_order=3, hp_threshold_pct=35, attack_multiplier=1.45, defense_multiplier=0.8,
            behavior_pattern=["void_rend", "void_rend", "abyssal_grasp"],
            transition_text="Бездна поглощает всё живое — финальная схватка!",
        ),
        dict(
            phase_order=4, hp_threshold_pct=15, attack_multiplier=1.7, defense_multiplier=0.6,
            behavior_pattern=["void_rend", "abyssal_grasp", "void_rend"],
            unlock_ability_code="abyssal_grasp",
            transition_text="Владыка Бездны обнажает истинную форму!",
        ),
    ],
}

# Campaign graph — 7 regions, 35 nodes, levels 1-100 (Stage 13 spec §11:
# a long campaign covering roughly the full level range, with varied
# regions/visual themes, branches, elites, and progressively harder
# bosses culminating in a final endgame boss). Still illustrative V1
# content/balance, not final tuning — same caveat as ENEMIES/EXPEDITIONS/
# QUESTS — but now a genuinely complete 1-100 arc, not just a template
# slice for the first regions.
CAMPAIGN_REGIONS = [
    dict(code="dark_forest", name="Тёмный лес", sort_order=1, description="Приграничные леса, кишащие гоблинами и волками."),
    dict(code="orcish_foothills", name="Орочьи предгорья", sort_order=2, description="Территория орочьих кланов у подножия гор."),
    dict(code="ashen_wastes", name="Пепельные пустоши", sort_order=3, description="Выжженные земли, где властвует огонь и лёд."),
    dict(code="dragon_ruins", name="Драконьи руины", sort_order=4, description="Древние руины, охраняемые последним драконом."),
    dict(code="sunken_catacombs", name="Забытые катакомбы", sort_order=5, description="Затопленные склепы, где мертвецы не знают покоя."),
    dict(code="sky_citadel", name="Небесная цитадель", sort_order=6, description="Парящая крепость древних стражей неба."),
    dict(code="abyss_gate", name="Врата Бездны", sort_order=7, description="Финальный рубеж — граница между миром живых и Бездной."),
]

# (code, region_code, name, node_type, enemy_name, level, depth, sort_order)
CAMPAIGN_NODES = [
    ("df_goblin_camp", "dark_forest", "Гоблинский лагерь", CampaignNodeType.battle, "Гоблин", 1, 0, 1),
    ("df_wolf_den", "dark_forest", "Волчье логово", CampaignNodeType.battle, "Лесной волк", 2, 1, 1),
    ("df_boar_thicket", "dark_forest", "Чаща кабанов", CampaignNodeType.battle, "Дикий кабан", 2, 1, 2),
    ("df_boneyard", "dark_forest", "Старое кладбище", CampaignNodeType.battle, "Скелет", 3, 2, 1),
    ("df_shaman_circle", "dark_forest", "Круг шамана", CampaignNodeType.elite, "Гоблин-шаман", 5, 2, 2),
    ("df_guardian_crypt", "dark_forest", "Склеп стража", CampaignNodeType.elite, "Костяной страж", 8, 3, 1),
    ("df_grove_ambush", "dark_forest", "Засада в роще", CampaignNodeType.battle, "Лесные разбойники", 10, 4, 1),

    ("of_orc_outpost", "orcish_foothills", "Орочья застава", CampaignNodeType.battle, "Орк-воин", 6, 5, 1),
    ("of_dark_tower", "orcish_foothills", "Тёмная башня", CampaignNodeType.battle, "Темный маг", 10, 6, 1),
    ("of_scout_camp", "orcish_foothills", "Лагерь разведчиков", CampaignNodeType.battle, "Орочий разведчик", 8, 6, 2),
    ("of_elite_camp", "orcish_foothills", "Лагерь элиты", CampaignNodeType.elite, "Элитный орк", 15, 7, 1),
    ("of_border_raid", "orcish_foothills", "Пограничный набег", CampaignNodeType.battle, "Орк-воин", 12, 7, 2),
    ("of_ritual_grounds", "orcish_foothills", "Ритуальная поляна", CampaignNodeType.elite, "Орочий жрец Гром", 18, 8, 1),
    ("of_warchief_throne", "orcish_foothills", "Трон вождя", CampaignNodeType.boss, "Вождь Оркхан", 20, 9, 1),

    ("aw_cinder_pass", "ashen_wastes", "Пепельный перевал", CampaignNodeType.battle, "Пепельный тролль", 22, 10, 1),
    ("aw_ember_field", "ashen_wastes", "Пылающее поле", CampaignNodeType.battle, "Огненный элементаль", 28, 11, 1),
    ("aw_frost_ridge", "ashen_wastes", "Ледяной хребет", CampaignNodeType.elite, "Ледяной страж", 34, 12, 1),
    ("aw_salamander_den", "ashen_wastes", "Логово саламандры", CampaignNodeType.elite, "Огненная саламандра", 31, 12, 2),
    ("aw_wastes_camp", "ashen_wastes", "Лагерь пустошей", CampaignNodeType.battle, "Лагерь пустошей", 36, 13, 1),

    ("dr_ruined_gate", "dragon_ruins", "Разрушенные врата", CampaignNodeType.battle, "Огненный элементаль", 38, 14, 1),
    ("dr_collapsed_hall", "dragon_ruins", "Обрушенный зал", CampaignNodeType.elite, "Каменный голем", 42, 15, 1),
    ("dr_dragon_lair", "dragon_ruins", "Логово дракона", CampaignNodeType.boss, "Древний дракон Иглаз", 45, 16, 1),

    ("sc_drowned_crypt", "sunken_catacombs", "Затопленный склеп", CampaignNodeType.battle, "Утопленный страж", 52, 17, 1),
    ("sc_bog_witch", "sunken_catacombs", "Логово ведьмы", CampaignNodeType.elite, "Болотная ведьма", 58, 18, 1),
    ("sc_bone_legion", "sunken_catacombs", "Костяной легион", CampaignNodeType.battle, "Легион костей", 58, 18, 2),
    ("sc_ossuary", "sunken_catacombs", "Оссуарий", CampaignNodeType.elite, "Хранитель оссуария", 64, 19, 1),
    ("sc_lich_throne", "sunken_catacombs", "Трон лича", CampaignNodeType.boss, "Лич Морвейн", 70, 20, 1),

    ("sk_ward_sentinel", "sky_citadel", "Пост стража", CampaignNodeType.battle, "Страж-часовой", 72, 21, 1),
    ("sk_storm_harpy", "sky_citadel", "Гнездо гарпий", CampaignNodeType.elite, "Буревая гарпия", 78, 22, 1),
    ("sk_iron_construct", "sky_citadel", "Кузня големов", CampaignNodeType.battle, "Железный голем", 78, 22, 2),
    ("sk_seraph_gate", "sky_citadel", "Врата серафима", CampaignNodeType.elite, "Страж врат Серафим", 84, 23, 1),
    ("sk_archon_boss", "sky_citadel", "Трон архонта", CampaignNodeType.boss, "Архонт Забвения", 90, 24, 1),

    ("ag_void_spawn", "abyss_gate", "Разлом пустоты", CampaignNodeType.battle, "Порождение Бездны", 92, 25, 1),
    ("ag_abyss_knight", "abyss_gate", "Застава рыцарей", CampaignNodeType.elite, "Рыцарь Бездны", 96, 26, 1),
    ("ag_final_boss", "abyss_gate", "Трон Владыки Бездны", CampaignNodeType.boss, "Владыка Бездны Некрон", 100, 27, 1),
]

# (from_code, to_code)
CAMPAIGN_EDGES = [
    ("df_goblin_camp", "df_wolf_den"),
    ("df_goblin_camp", "df_boar_thicket"),
    ("df_wolf_den", "df_boneyard"),
    ("df_wolf_den", "df_shaman_circle"),
    ("df_boar_thicket", "df_boneyard"),
    ("df_boneyard", "df_guardian_crypt"),
    ("df_shaman_circle", "df_guardian_crypt"),
    ("df_guardian_crypt", "df_grove_ambush"),
    ("df_grove_ambush", "of_orc_outpost"),

    ("of_orc_outpost", "of_dark_tower"),
    ("of_orc_outpost", "of_scout_camp"),
    ("of_dark_tower", "of_elite_camp"),
    ("of_dark_tower", "of_border_raid"),
    ("of_scout_camp", "of_border_raid"),
    ("of_elite_camp", "of_ritual_grounds"),
    ("of_border_raid", "of_ritual_grounds"),
    ("of_ritual_grounds", "of_warchief_throne"),

    ("of_warchief_throne", "aw_cinder_pass"),
    ("aw_cinder_pass", "aw_ember_field"),
    ("aw_ember_field", "aw_frost_ridge"),
    ("aw_ember_field", "aw_salamander_den"),
    ("aw_frost_ridge", "aw_wastes_camp"),
    ("aw_salamander_den", "aw_wastes_camp"),
    ("aw_wastes_camp", "dr_ruined_gate"),

    ("dr_ruined_gate", "dr_collapsed_hall"),
    ("dr_collapsed_hall", "dr_dragon_lair"),

    ("dr_dragon_lair", "sc_drowned_crypt"),
    ("sc_drowned_crypt", "sc_bog_witch"),
    ("sc_drowned_crypt", "sc_bone_legion"),
    ("sc_bog_witch", "sc_ossuary"),
    ("sc_bone_legion", "sc_ossuary"),
    ("sc_ossuary", "sc_lich_throne"),

    ("sc_lich_throne", "sk_ward_sentinel"),
    ("sk_ward_sentinel", "sk_storm_harpy"),
    ("sk_ward_sentinel", "sk_iron_construct"),
    ("sk_storm_harpy", "sk_seraph_gate"),
    ("sk_iron_construct", "sk_seraph_gate"),
    ("sk_seraph_gate", "sk_archon_boss"),

    ("sk_archon_boss", "ag_void_spawn"),
    ("ag_void_spawn", "ag_abyss_knight"),
    ("ag_abyss_knight", "ag_final_boss"),
]

# ItemEffect rows, attached to specific (slot, tier, rarity) item
# templates — demonstrates the spec's own synergy example ("Fire Skill ->
# Burn -> Ring bonus against burning targets -> increased damage") and
# that higher rarity unlocks a qualitatively different build option, not
# just bigger flat numbers (Stage 13 spec §10): the epic Ring below grants
# a Burn-on-crit + bonus-vs-Burn combo no common/rare ring has access to,
# and the legendary Amulet grants lifesteal, a mechanic no lower rarity of
# that slot grants at all.
ITEM_EFFECTS = [
    dict(
        slot=EquipmentSlot.ring, tier=6, rarity=Rarity.epic,
        effects=[
            dict(trigger=ItemEffectTrigger.on_crit, effect_type=ItemEffectType.apply_status, status_label="burn", magnitude=6, duration_turns=3),
            dict(trigger=ItemEffectTrigger.on_hit_dealt, effect_type=ItemEffectType.damage_bonus_vs_status, status_label="burn", magnitude=20),
        ],
    ),
    dict(
        slot=EquipmentSlot.amulet, tier=8, rarity=Rarity.legendary,
        effects=[
            dict(trigger=ItemEffectTrigger.on_hit_dealt, effect_type=ItemEffectType.lifesteal_pct, magnitude=10),
        ],
    ),
    dict(
        slot=EquipmentSlot.armor, tier=5, rarity=Rarity.epic,
        effects=[
            dict(trigger=ItemEffectTrigger.on_defend, effect_type=ItemEffectType.shield_bonus_pct, magnitude=15),
        ],
    ),
]


# Illustrative V1 balance, not final tuning — same caveat as CLASSES/ENEMIES.
# duration_seconds is authored directly (no formula, same as EnemyTemplate).
EXPEDITIONS = [
    dict(
        name="Тренировочный лагерь", sort_order=1, duration_seconds=5 * 60, required_hero_level=1,
        reward_xp=25, reward_coins=10,
        description="Короткая тренировка для начинающих героев.",
    ),
    dict(
        name="Гоблинский лес", sort_order=2, duration_seconds=30 * 60, required_hero_level=5,
        reward_xp=100, reward_coins=50,
        description="Разведка леса, кишащего гоблинами.",
    ),
    dict(
        name="Древние руины", sort_order=3, duration_seconds=2 * 60 * 60, required_hero_level=15,
        reward_xp=400, reward_coins=200,
        description="Опасная экспедиция в руины забытой цивилизации.",
    ),
    dict(
        name="Драконья долина", sort_order=4, duration_seconds=8 * 60 * 60, required_hero_level=30,
        reward_xp=1200, reward_coins=700,
        description="Долгий и рискованный поход в земли драконов.",
    ),
]


# Illustrative V1 balance, not final tuning — same caveat as ENEMIES/
# EXPEDITIONS. One quest per V1 condition_type so every branch of
# quest_progression.get_quest_progress is exercised by real seed data.
QUESTS = [
    dict(
        code="first_victory", name="Первая победа", sort_order=1,
        condition_type=QuestConditionType.battles_won, target_value=1,
        reward_xp=20, reward_coins=15,
        description="Одержите первую победу в бою.",
    ),
    dict(
        code="veteran_warrior", name="Опытный воин", sort_order=2,
        condition_type=QuestConditionType.battles_won, target_value=5,
        reward_xp=80, reward_coins=50,
        description="Одержите 5 побед в боях.",
    ),
    dict(
        code="explorer", name="Исследователь", sort_order=3,
        condition_type=QuestConditionType.expeditions_claimed, target_value=1,
        reward_xp=30, reward_coins=20,
        description="Завершите первую экспедицию.",
    ),
    dict(
        code="wealth", name="Богатство", sort_order=4,
        condition_type=QuestConditionType.chests_opened, target_value=3,
        reward_xp=40, reward_coins=30,
        description="Откройте 3 сундука.",
    ),
    dict(
        code="hero_growth", name="Рост героя", sort_order=5,
        condition_type=QuestConditionType.hero_level, target_value=5,
        reward_xp=0, reward_coins=100,
        description="Достигните 5 уровня героя.",
    ),
    dict(
        code="equipment", name="Экипировка", sort_order=6,
        condition_type=QuestConditionType.items_equipped, target_value=3,
        reward_xp=50, reward_coins=40,
        description="Экипируйте 3 предмета одновременно.",
    ),
    dict(
        code="skill_master", name="Мастер навыков", sort_order=7,
        condition_type=QuestConditionType.skills_upgraded, target_value=5,
        reward_xp=100, reward_coins=60,
        description="Улучшите навыки героя суммарно 5 раз.",
    ),
    # A deeper pool feeding the 5-active-slot rotation (quest_service.
    # ACTIVE_QUEST_SLOT_COUNT) — more tiers of the original 6 condition
    # types plus two new ones tied to Stage 13 content (arena_wins,
    # campaign_nodes_cleared). Still illustrative V1 balance.
    dict(
        code="battles_won_15", name="Закалённый в боях", sort_order=8,
        condition_type=QuestConditionType.battles_won, target_value=15,
        reward_xp=180, reward_coins=120,
        description="Одержите 15 побед в боях.",
    ),
    dict(
        code="battles_won_30", name="Гроза монстров", sort_order=9,
        condition_type=QuestConditionType.battles_won, target_value=30,
        reward_xp=350, reward_coins=240,
        description="Одержите 30 побед в боях.",
    ),
    dict(
        code="battles_won_60", name="Легенда боя", sort_order=10,
        condition_type=QuestConditionType.battles_won, target_value=60,
        reward_xp=700, reward_coins=480,
        description="Одержите 60 побед в боях.",
    ),
    dict(
        code="expeditions_claimed_5", name="Бывалый путешественник", sort_order=11,
        condition_type=QuestConditionType.expeditions_claimed, target_value=5,
        reward_xp=120, reward_coins=80,
        description="Завершите 5 экспедиций.",
    ),
    dict(
        code="expeditions_claimed_15", name="Покоритель троп", sort_order=12,
        condition_type=QuestConditionType.expeditions_claimed, target_value=15,
        reward_xp=300, reward_coins=200,
        description="Завершите 15 экспедиций.",
    ),
    dict(
        code="chests_opened_10", name="Коллекционер", sort_order=13,
        condition_type=QuestConditionType.chests_opened, target_value=10,
        reward_xp=140, reward_coins=100,
        description="Откройте 10 сундуков.",
    ),
    dict(
        code="chests_opened_25", name="Охотник за сокровищами", sort_order=14,
        condition_type=QuestConditionType.chests_opened, target_value=25,
        reward_xp=320, reward_coins=220,
        description="Откройте 25 сундуков.",
    ),
    dict(
        code="hero_growth_15", name="Восходящая звезда", sort_order=15,
        condition_type=QuestConditionType.hero_level, target_value=15,
        reward_xp=0, reward_coins=250,
        description="Достигните 15 уровня героя.",
    ),
    dict(
        code="hero_growth_30", name="Опытный герой", sort_order=16,
        condition_type=QuestConditionType.hero_level, target_value=30,
        reward_xp=0, reward_coins=500,
        description="Достигните 30 уровня героя.",
    ),
    dict(
        code="hero_growth_50", name="Закалённый герой", sort_order=17,
        condition_type=QuestConditionType.hero_level, target_value=50,
        reward_xp=0, reward_coins=900,
        description="Достигните 50 уровня героя.",
    ),
    dict(
        code="hero_growth_75", name="Легенда королевства", sort_order=18,
        condition_type=QuestConditionType.hero_level, target_value=75,
        reward_xp=0, reward_coins=1500,
        description="Достигните 75 уровня героя.",
    ),
    dict(
        code="equipment_5", name="Полное снаряжение", sort_order=19,
        condition_type=QuestConditionType.items_equipped, target_value=5,
        reward_xp=150, reward_coins=110,
        description="Экипируйте 5 предметов одновременно.",
    ),
    dict(
        code="equipment_7", name="С головы до пят", sort_order=20,
        condition_type=QuestConditionType.items_equipped, target_value=7,
        reward_xp=280, reward_coins=200,
        description="Экипируйте все 7 предметов одновременно.",
    ),
    dict(
        code="skill_master_15", name="Знаток тактики", sort_order=21,
        condition_type=QuestConditionType.skills_upgraded, target_value=15,
        reward_xp=260, reward_coins=180,
        description="Улучшите навыки героя суммарно 15 раз.",
    ),
    dict(
        code="skill_master_30", name="Мастер боевого искусства", sort_order=22,
        condition_type=QuestConditionType.skills_upgraded, target_value=30,
        reward_xp=520, reward_coins=360,
        description="Улучшите навыки героя суммарно 30 раз.",
    ),
    dict(
        code="arena_wins_1", name="Первая кровь на арене", sort_order=23,
        condition_type=QuestConditionType.arena_wins, target_value=1,
        reward_xp=60, reward_coins=40,
        description="Одержите первую победу на арене.",
    ),
    dict(
        code="arena_wins_5", name="Дуэлянт", sort_order=24,
        condition_type=QuestConditionType.arena_wins, target_value=5,
        reward_xp=200, reward_coins=140,
        description="Одержите 5 побед на арене.",
    ),
    dict(
        code="arena_wins_15", name="Чемпион арены", sort_order=25,
        condition_type=QuestConditionType.arena_wins, target_value=15,
        reward_xp=450, reward_coins=320,
        description="Одержите 15 побед на арене.",
    ),
    dict(
        code="arena_wins_30", name="Непобедимый", sort_order=26,
        condition_type=QuestConditionType.arena_wins, target_value=30,
        reward_xp=850, reward_coins=600,
        description="Одержите 30 побед на арене.",
    ),
    dict(
        code="campaign_nodes_1", name="Первые шаги в поход", sort_order=27,
        condition_type=QuestConditionType.campaign_nodes_cleared, target_value=1,
        reward_xp=40, reward_coins=25,
        description="Пройдите первый узел кампании.",
    ),
    dict(
        code="campaign_nodes_5", name="По следам легенды", sort_order=28,
        condition_type=QuestConditionType.campaign_nodes_cleared, target_value=5,
        reward_xp=160, reward_coins=110,
        description="Пройдите 5 узлов кампании.",
    ),
    dict(
        code="campaign_nodes_15", name="Покоритель регионов", sort_order=29,
        condition_type=QuestConditionType.campaign_nodes_cleared, target_value=15,
        reward_xp=420, reward_coins=300,
        description="Пройдите 15 узлов кампании.",
    ),
    dict(
        code="campaign_nodes_30", name="Странник по мирам", sort_order=30,
        condition_type=QuestConditionType.campaign_nodes_cleared, target_value=30,
        reward_xp=900, reward_coins=650,
        description="Пройдите 30 узлов кампании.",
    ),
    dict(
        code="campaign_nodes_50", name="Победитель Бездны", sort_order=31,
        condition_type=QuestConditionType.campaign_nodes_cleared, target_value=50,
        reward_xp=1800, reward_coins=1300,
        description="Пройдите 50 узлов кампании.",
    ),
]

# Fixed, admin-uploadable icon slots — replaces every hardcoded emoji in
# the bottom nav, the Battle hub's mode/mini-game rows, and the More page
# rows. The set of keys is closed and matches the frontend's own hardcoded
# UI elements exactly; there is no "add a new slot" admin flow (see
# AppIcon's docstring) — only upload/replace an image for an existing key.
APP_ICONS = [
    ("nav_chests", "Нижнее меню — Сундуки"),
    ("nav_battle", "Нижнее меню — Битвы"),
    ("nav_hero", "Нижнее меню — Герой"),
    ("nav_inventory", "Нижнее меню — Инвентарь"),
    ("nav_more", "Нижнее меню — Ещё"),
    ("mode_campaign", "Битвы — Кампания"),
    ("mode_arena", "Битвы — Арена"),
    ("minigame_memory", "Мини-игра — Запомни последовательность"),
    ("minigame_pairs", "Мини-игра — Найди пару"),
    ("minigame_dummy", "Мини-игра — Боевой манекен"),
    ("minigame_alchemy", "Мини-игра — Алхимия"),
    ("minigame_dice", "Мини-игра — Тавернные кости"),
    ("minigame_cups", "Мини-игра — Три кубка"),
    ("more_collection", "Ещё — Коллекция"),
    ("more_bestiary", "Ещё — Бестиарий"),
    ("more_quests", "Ещё — Квесты"),
    ("more_expeditions", "Ещё — Экспедиции"),
    ("more_leaderboards", "Ещё — Лидерборды"),
    ("more_equipment", "Ещё — Экипировка"),
    ("more_statistics", "Ещё — Статистика"),
    ("more_settings", "Ещё — Настройки"),
]


async def _get_or_create_quest_definition(db: AsyncSession, data: dict) -> QuestDefinition:
    result = await db.execute(select(QuestDefinition).where(QuestDefinition.code == data["code"]))
    quest = result.scalar_one_or_none()
    if quest is None:
        quest = QuestDefinition(**data)
        db.add(quest)
        await db.flush()
    return quest


async def _get_or_create_app_icon(db: AsyncSession, key: str, label: str) -> AppIcon:
    result = await db.execute(select(AppIcon).where(AppIcon.key == key))
    icon = result.scalar_one_or_none()
    if icon is None:
        icon = AppIcon(key=key, label=label, image_path=None)
        db.add(icon)
        await db.flush()
    return icon


async def _get_or_create_expedition_template(db: AsyncSession, data: dict) -> ExpeditionTemplate:
    result = await db.execute(select(ExpeditionTemplate).where(ExpeditionTemplate.name == data["name"]))
    expedition = result.scalar_one_or_none()
    if expedition is None:
        expedition = ExpeditionTemplate(**data)
        db.add(expedition)
        await db.flush()
    return expedition


async def _get_or_create_enemy_template(db: AsyncSession, data: dict) -> EnemyTemplate:
    result = await db.execute(select(EnemyTemplate).where(EnemyTemplate.name == data["name"]))
    enemy = result.scalar_one_or_none()
    if enemy is None:
        enemy = EnemyTemplate(**data)
        db.add(enemy)
        await db.flush()
    return enemy


async def _get_or_create_enemy_ability(db: AsyncSession, enemy_id: int, data: dict) -> EnemyAbility:
    result = await db.execute(
        select(EnemyAbility).where(EnemyAbility.enemy_template_id == enemy_id, EnemyAbility.code == data["code"])
    )
    ability = result.scalar_one_or_none()
    if ability is None:
        ability = EnemyAbility(enemy_template_id=enemy_id, **data)
        db.add(ability)
        await db.flush()
    return ability


async def _get_or_create_enemy_resistance(db: AsyncSession, enemy_id: int, data: dict) -> EnemyResistance:
    result = await db.execute(
        select(EnemyResistance).where(
            EnemyResistance.enemy_template_id == enemy_id, EnemyResistance.status_label == data["status_label"]
        )
    )
    resistance = result.scalar_one_or_none()
    if resistance is None:
        resistance = EnemyResistance(enemy_template_id=enemy_id, **data)
        db.add(resistance)
        await db.flush()
    return resistance


async def _get_or_create_boss_phase(db: AsyncSession, enemy_id: int, data: dict) -> BossPhase:
    result = await db.execute(
        select(BossPhase).where(BossPhase.enemy_template_id == enemy_id, BossPhase.phase_order == data["phase_order"])
    )
    phase = result.scalar_one_or_none()
    if phase is None:
        phase = BossPhase(enemy_template_id=enemy_id, **data)
        db.add(phase)
        await db.flush()
    return phase


async def _get_or_create_item_effect(db: AsyncSession, item_template_id: int, data: dict) -> ItemEffect:
    result = await db.execute(
        select(ItemEffect).where(
            ItemEffect.item_template_id == item_template_id,
            ItemEffect.trigger == data["trigger"],
            ItemEffect.effect_type == data["effect_type"],
        )
    )
    effect = result.scalar_one_or_none()
    if effect is None:
        effect = ItemEffect(item_template_id=item_template_id, **data)
        db.add(effect)
        await db.flush()
    return effect


async def _get_or_create_campaign_region(db: AsyncSession, data: dict) -> CampaignRegion:
    result = await db.execute(select(CampaignRegion).where(CampaignRegion.code == data["code"]))
    region = result.scalar_one_or_none()
    if region is None:
        region = CampaignRegion(**data)
        db.add(region)
        await db.flush()
    return region


async def _get_or_create_campaign_node(
    db: AsyncSession, code: str, region_id: int, name: str, node_type: CampaignNodeType,
    enemy_template_id: int | None, level: int, depth: int, sort_order: int,
) -> CampaignNode:
    result = await db.execute(select(CampaignNode).where(CampaignNode.code == code))
    node = result.scalar_one_or_none()
    if node is None:
        node = CampaignNode(
            code=code, region_id=region_id, name=name, node_type=node_type,
            enemy_template_id=enemy_template_id, level=level, depth=depth, sort_order=sort_order,
        )
        db.add(node)
        await db.flush()
    return node


async def _get_or_create_campaign_node_edge(db: AsyncSession, from_node_id: int, to_node_id: int) -> None:
    result = await db.execute(
        select(CampaignNodeEdge).where(CampaignNodeEdge.from_node_id == from_node_id, CampaignNodeEdge.to_node_id == to_node_id)
    )
    if result.scalar_one_or_none() is None:
        db.add(CampaignNodeEdge(from_node_id=from_node_id, to_node_id=to_node_id))
        await db.flush()


async def _get_or_create_race(db: AsyncSession, data: dict) -> Race:
    result = await db.execute(select(Race).where(Race.code == data["code"]))
    race = result.scalar_one_or_none()
    if race is None:
        race = Race(**data)
        db.add(race)
        await db.flush()
    return race


async def _get_or_create_class(db: AsyncSession, data: dict) -> CharacterClass:
    result = await db.execute(select(CharacterClass).where(CharacterClass.code == data["code"]))
    char_class = result.scalar_one_or_none()
    if char_class is None:
        char_class = CharacterClass(**data)
        db.add(char_class)
        await db.flush()
    return char_class


async def _get_or_create_hero_template(
    db: AsyncSession, name: str, race_id: int, class_id: int, sort_order: int, description: str | None
) -> HeroTemplate:
    result = await db.execute(select(HeroTemplate).where(HeroTemplate.name == name))
    template = result.scalar_one_or_none()
    if template is None:
        template = HeroTemplate(
            name=name, race_id=race_id, class_id=class_id, sort_order=sort_order, description=description
        )
        db.add(template)
        await db.flush()
    return template


async def _get_or_create_skill_definition(db: AsyncSession, class_id: int, data: dict) -> SkillDefinition:
    result = await db.execute(
        select(SkillDefinition).where(SkillDefinition.class_id == class_id, SkillDefinition.code == data["code"])
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        skill = SkillDefinition(class_id=class_id, **data)
        db.add(skill)
        await db.flush()
    return skill


async def _get_or_create_item_template(
    db: AsyncSession, slot: EquipmentSlot, tier: int, rarity: Rarity, sort_order: int
) -> ItemTemplate:
    # Keyed by (slot, tier, rarity), not name — name is now a pure display
    # string shared across all 4 rarities of the same (slot, tier) (see
    # ITEM_NAMES_RU's docstring), so it's no longer a usable identity key.
    result = await db.execute(
        select(ItemTemplate).where(
            ItemTemplate.slot == slot, ItemTemplate.tier == tier, ItemTemplate.rarity == rarity
        )
    )
    template = result.unique().scalar_one_or_none()
    if template is None:
        template = ItemTemplate(
            slot=slot, tier=tier, rarity=rarity, name=_item_name(slot, tier), sort_order=sort_order
        )
        db.add(template)
        await db.flush()
        for stat_type in RARITY_AFFIX_STATS[rarity]:
            db.add(ItemAffix(item_template_id=template.id, stat_type=stat_type))
        await db.flush()
    return template


async def _get_or_create_chest(db: AsyncSession, quality: int) -> Chest:
    slug = f"tier-{quality}-chest"
    result = await db.execute(select(Chest).where(Chest.slug == slug))
    chest = result.unique().scalar_one_or_none()
    if chest is None:
        chest = Chest(
            slug=slug,
            name=CHEST_NAMES[quality],
            description="Содержит предмет экипировки — тир ограничен уровнем вашего героя.",
            price=CHEST_PRICES[quality],
            sort_order=quality,
        )
        db.add(chest)
        await db.flush()
        for rarity, probability in _chest_rarity_probabilities(quality).items():
            db.add(ChestRarityProbability(chest_id=chest.id, rarity=rarity, probability=probability))
        await db.flush()
    return chest


async def _get_or_create_free_chest(db: AsyncSession) -> Chest:
    # slug must match free_chest_service.FREE_CHEST_SLUG — imported there
    # rather than duplicated as a second literal.
    result = await db.execute(select(Chest).where(Chest.slug == FREE_CHEST_SLUG))
    chest = result.unique().scalar_one_or_none()
    if chest is None:
        chest = Chest(
            slug=FREE_CHEST_SLUG,
            name="Бесплатный сундук",
            description="Доступен каждые 24 часа. Содержит предмет экипировки — тир ограничен уровнем вашего героя.",
            price=0,
            sort_order=0,
        )
        db.add(chest)
        await db.flush()
        for rarity, probability in _chest_rarity_probabilities(1).items():
            db.add(ChestRarityProbability(chest_id=chest.id, rarity=rarity, probability=probability))
        await db.flush()
    return chest


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        races = {}
        for data in RACES:
            races[data["code"]] = await _get_or_create_race(db, data)

        classes = {}
        for data in CLASSES:
            classes[data["code"]] = await _get_or_create_class(db, data)

        for class_code, skills in SKILLS.items():
            for skill_data in skills:
                await _get_or_create_skill_definition(db, classes[class_code].id, skill_data)

        item_sort_order = 1
        item_templates = {}
        for tier in range(1, 11):
            for slot in ALL_SLOTS:
                for rarity in ALL_RARITIES:
                    item_templates[(slot, tier, rarity)] = await _get_or_create_item_template(
                        db, slot, tier, rarity, item_sort_order
                    )
                    item_sort_order += 1

        for quality in range(1, 11):
            await _get_or_create_chest(db, quality)

        await _get_or_create_free_chest(db)

        for tpl in HERO_TEMPLATES:
            await _get_or_create_hero_template(
                db,
                name=str(tpl["name"]),
                race_id=races[str(tpl["race"])].id,
                class_id=classes[str(tpl["cls"])].id,
                sort_order=int(tpl["sort_order"]),
                description=str(tpl["description"]),
            )

        enemies = {}
        for data in ENEMIES:
            enemies[data["name"]] = await _get_or_create_enemy_template(db, data)

        for enemy_name, abilities in ENEMY_ABILITIES.items():
            for ability_data in abilities:
                await _get_or_create_enemy_ability(db, enemies[enemy_name].id, ability_data)

        for enemy_name, resistances in ENEMY_RESISTANCES.items():
            for resistance_data in resistances:
                await _get_or_create_enemy_resistance(db, enemies[enemy_name].id, resistance_data)

        for enemy_name, phases in BOSS_PHASES.items():
            for phase_data in phases:
                await _get_or_create_boss_phase(db, enemies[enemy_name].id, phase_data)

        for entry in ITEM_EFFECTS:
            template = item_templates[(entry["slot"], entry["tier"], entry["rarity"])]
            for effect_data in entry["effects"]:
                await _get_or_create_item_effect(db, template.id, effect_data)

        for data in EXPEDITIONS:
            await _get_or_create_expedition_template(db, data)

        for data in QUESTS:
            await _get_or_create_quest_definition(db, data)

        for key, label in APP_ICONS:
            await _get_or_create_app_icon(db, key, label)

        regions = {}
        for data in CAMPAIGN_REGIONS:
            regions[data["code"]] = await _get_or_create_campaign_region(db, data)

        nodes = {}
        for code, region_code, name, node_type, enemy_name, level, depth, sort_order in CAMPAIGN_NODES:
            nodes[code] = await _get_or_create_campaign_node(
                db, code, regions[region_code].id, name, node_type, enemies[enemy_name].id, level, depth, sort_order
            )

        for from_code, to_code in CAMPAIGN_EDGES:
            await _get_or_create_campaign_node_edge(db, nodes[from_code].id, nodes[to_code].id)

        await db.commit()
    print("RPG catalog seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
