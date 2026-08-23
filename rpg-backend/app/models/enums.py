import enum


class SkillType(str, enum.Enum):
    """Describes what a skill will eventually DO once the battle engine
    exists (Stage 8/9) — purely descriptive data in Stage 3. No damage/
    heal/buff/debuff/DoT/stun/shield is actually computed or applied here."""

    damage = "damage"
    heal = "heal"
    buff = "buff"
    debuff = "debuff"
    dot = "dot"
    shield = "shield"
    stun = "stun"


class EquipmentSlot(str, enum.Enum):
    weapon = "weapon"
    helmet = "helmet"
    armor = "armor"
    boots = "boots"
    gloves = "gloves"
    ring = "ring"
    amulet = "amulet"


class Rarity(str, enum.Enum):
    common = "common"
    rare = "rare"
    epic = "epic"
    legendary = "legendary"


# Ordinal comparison for rarity (e.g. "did this roll meet a guaranteed
# minimum rarity") — same shape as the football app's RARITY_ORDER.
RARITY_ORDER: dict[Rarity, int] = {
    Rarity.common: 0,
    Rarity.rare: 1,
    Rarity.epic: 2,
    Rarity.legendary: 3,
}


class TransactionType(str, enum.Enum):
    """Kept intentionally small — only the sources that actually exist in
    this backend today. Extend as later stages add real coin sources/sinks
    (quests, PvE/PvP rewards, expeditions, ...); don't pre-add speculative
    values the football app has but nothing here can trigger yet."""

    chest_purchase = "chest_purchase"
    admin_grant = "admin_grant"
    admin_deduct = "admin_deduct"
    battle_reward = "battle_reward"
    expedition_reward = "expedition_reward"
    quest_reward = "quest_reward"
    arena_reward = "arena_reward"
    referral_reward = "referral_reward"
    minigame_reward = "minigame_reward"
    campaign_reward = "campaign_reward"


class MinigameType(str, enum.Enum):
    """Kept intentionally small like TransactionType — only the mini-games
    that actually exist. Extend as later passes add more (the hub screen's
    docstring flags this as an open list)."""

    memory = "memory"
    pairs = "pairs"
    dummy = "dummy"
    alchemy = "alchemy"
    dice = "dice"
    cups = "cups"


class MinigameAttemptStatus(str, enum.Enum):
    """`pending` covers two different shapes depending on the game: for
    Memory Sequence/Alchemy/Training Dummy, "pending" means exactly one
    resolving call is still owed (start already happened, submit/complete
    hasn't yet) — same as BattleResult's single-shot framing. For Tavern
    Dice/Three Cups, "pending" instead spans however many roll/guess calls
    the player makes before banking or losing — genuinely multi-step
    server-side state, not a single request/response pair. Either way,
    `completed` is still the one and only terminal state a row ever
    reaches."""

    pending = "pending"
    completed = "completed"


class BattleResult(str, enum.Enum):
    """Deliberately binary — no RUNNING/pending state exists because a
    battle resolves fully synchronously in one request (see battle_service
    .start_battle / ARCHITECTURE.md's Stage 6 section); nothing is ever
    persisted mid-fight. A round-cap stalemate is resolved by remaining
    HP% (hero wins ties), never stored as a third "draw" value."""

    won = "won"
    lost = "lost"


class ExpeditionStatus(str, enum.Enum):
    """Only 2 values are ever WRITTEN by application code. "completed" is
    deliberately never a third persisted state — same "derive, don't store"
    call as BattleResult choosing not to store a pending/draw value. An
    expedition becomes completed purely by time passing
    (started_at + duration <= now); persisting that transition would need
    something to perform it, i.e. a background job, which Stage 7 explicitly
    must not have. The API layer (expedition_service._status_out) still
    exposes "running"/"completed"/"claimed" to clients — computed at read
    time from this 2-value column + `completed_at`, never stored as a third
    enum value. See ARCHITECTURE.md's Stage 7 section."""

    running = "running"
    claimed = "claimed"


class ItemStatType(str, enum.Enum):
    """The 4 stats equipment can grant. Deliberately excludes crit_chance/
    crit_damage: those are fractional/multiplier values on a totally
    different numeric scale than hp/attack/defense/speed, and the tier
    power curve (built for the additive stats) would need a separate,
    heavily-dampened formula to make sense there. V1 keeps crit as a
    pure class stat; itemized crit is a clean later addition, not a
    change to what's built here."""

    hp = "hp"
    attack = "attack"
    defense = "defense"
    speed = "speed"


class QuestConditionType(str, enum.Enum):
    """What a quest's progress counts, and against what scope. All 6 are
    computed by querying EXISTING tables (Battle/UserExpedition/
    ChestOpening/UserHero/UserItem/CharacterSkill) — no new tables record
    progress, no other service pushes updates into a quest ledger. See
    services/quest_progression.py for the query behind each value.

    battles_won/expeditions_claimed/chests_opened/skills_upgraded are
    lifetime cumulative counts (never decrease). hero_level/items_equipped
    are current-state snapshots (can decrease — a hero can be un-equipped,
    though nothing currently lowers hero.level). Both kinds are computed
    the same way — a live query, once, at read/claim time — so quests don't
    need to special-case which kind a condition_type is."""

    battles_won = "battles_won"
    expeditions_claimed = "expeditions_claimed"
    chests_opened = "chests_opened"
    hero_level = "hero_level"
    items_equipped = "items_equipped"
    skills_upgraded = "skills_upgraded"
    # Stage 13 additions — arena_wins counts finished ArenaMatch rows won;
    # campaign_nodes_cleared counts distinct UserCampaignNodeClear rows
    # (first clears only, not repeat-clear counts).
    arena_wins = "arena_wins"
    campaign_nodes_cleared = "campaign_nodes_cleared"


class ArenaMatchStatus(str, enum.Enum):
    """Binary, same reasoning as BattleResult/ExpeditionStatus: no
    "pending_accept"/"matchmaking" state exists because Stage 9's V1 has no
    accept-flow or matchmaking (a challenge immediately creates a running
    match) and no in-between state a background job would need to advance —
    every transition within a `running` match (whose action is pending,
    which round it's on, whether it's overdue) lives in `state`/
    `round_deadline_at` and is computed at read/action time, never a third
    stored status value. See ARCHITECTURE.md's Stage 9 section."""

    running = "running"
    finished = "finished"


class CampaignBattleStatus(str, enum.Enum):
    """Binary, same reasoning as ArenaMatchStatus — a CampaignBattle is a
    single-player session with no opponent to wait on, so there is no
    third "waiting on the other side" state either. Everything within a
    `running` battle (whose round it's on, the queued enemy intent, boss
    phase) lives in `server_state`, computed/mutated at action time, never
    a third stored status value. See campaign_battle_service.py."""

    running = "running"
    finished = "finished"


class CampaignNodeType(str, enum.Enum):
    """battle/elite/boss are the only types Stage 13 actually implements —
    a node's type picks the enemy roster (single enemy vs elite-tier vs
    EnemyTemplate.is_boss) and reward tier, nothing else. story_event/
    treasure/merchant/rest are reserved so the campaign graph schema
    doesn't need a migration to grow into them later, but no service or
    frontend screen handles them yet — do not build handling for them
    without necessity (Stage 13 spec, §23)."""

    battle = "battle"
    elite = "elite"
    boss = "boss"
    story_event = "story_event"
    treasure = "treasure"
    merchant = "merchant"
    rest = "rest"


class ItemEffectTrigger(str, enum.Enum):
    """When an ItemEffect fires during campaign combat resolution. `passive`
    effects apply continuously (e.g. a flat shield-on-round-start) rather
    than in response to a specific combat event."""

    on_crit = "on_crit"
    on_defend = "on_defend"
    on_hit_dealt = "on_hit_dealt"
    on_hit_taken = "on_hit_taken"
    on_status_applied = "on_status_applied"
    passive = "passive"


class ItemEffectType(str, enum.Enum):
    """What an ItemEffect actually does once its trigger fires. Kept as a
    small closed set resolved by an explicit handler dict in
    campaign_battle_service.py — deliberately not a scripting engine
    (Stage 13 spec, §10)."""

    apply_status = "apply_status"
    damage_bonus_vs_status = "damage_bonus_vs_status"
    shield_bonus_pct = "shield_bonus_pct"
    lifesteal_pct = "lifesteal_pct"
