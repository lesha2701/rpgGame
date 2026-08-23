from typing import Literal

from pydantic import BaseModel

from app.schemas.battle import BattleLogEntryOut


class CampaignSkillOut(BaseModel):
    """One of the hero's LEARNED skills, with round-accurate cooldown state
    — the frontend hides a skill button entirely if the hero hasn't
    learned it (this list only ever contains learned skills, same source
    as PvE/Arena's own skill snapshot) and shows a disabled state +
    cooldown_remaining when it isn't ready yet (Stage 13 spec §14-20)."""

    skill_definition_id: int
    name: str
    skill_type: str
    cooldown_turns: int
    cooldown_remaining: int
    is_interrupt: bool


class CampaignHeroStateOut(BaseModel):
    current_hp: int
    max_hp: int
    attack_bonus: float
    buff_turns_remaining: int
    defense_bonus: float
    defense_buff_turns_remaining: int
    shield_remaining: float
    stunned: bool
    dot_turns_remaining: int
    skills: list[CampaignSkillOut]


class CampaignEnemyIntentOut(BaseModel):
    """Enemy Intent — a conditional promise, not a guaranteed action (Stage
    13 spec §7): "what the enemy will do if it's still able to when its
    turn comes." min_damage/max_damage are the non-crit/crit preview for a
    damage-type ability (None for buff/shield/dot/stun/debuff intents,
    which don't hit for a number)."""

    ability_code: str | None
    name: str
    skill_type: str
    status_label: str | None
    min_damage: int | None
    max_damage: int | None


class CampaignEnemyStateOut(BaseModel):
    enemy_template_id: int
    name: str
    image_path: str | None
    level: int
    is_boss: bool
    current_hp: int
    max_hp: int
    shield_remaining: float
    stunned: bool
    dot_turns_remaining: int
    phase_order: int | None
    intent: CampaignEnemyIntentOut | None


class CampaignBattleOut(BaseModel):
    id: int
    node_id: int
    status: str
    current_round: int
    hero: CampaignHeroStateOut
    enemy: CampaignEnemyStateOut
    log: list[BattleLogEntryOut]
    result: str | None
    reward_xp: int
    reward_coins: int
    is_first_clear: bool
    created_at: str
    finished_at: str | None


class StartCampaignBattleRequest(BaseModel):
    node_id: int


class CampaignActionRequest(BaseModel):
    # Same stale/idempotent-replay purpose as ArenaActionRequest.round —
    # see campaign_battle_service.submit_campaign_action. "defend" has no
    # ArenaActionRequest counterpart — PvP never needed a pure-mitigation
    # action, Campaign's non-reactive-play requirements do (Stage 13 spec
    # §4/§14-20).
    round: int
    action_type: Literal["basic_attack", "skill", "defend"]
    skill_id: int | None = None


class CampaignNodeOut(BaseModel):
    id: int
    region_id: int
    code: str
    name: str
    node_type: str
    enemy_template_id: int | None
    enemy_name: str | None
    enemy_image_path: str | None
    enemy_level: int | None
    level: int
    depth: int
    sort_order: int
    completed: bool
    available: bool
    is_current: bool
    clear_count: int


class CampaignRegionOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    image_path: str | None
    sort_order: int
    nodes: list[CampaignNodeOut]


class CampaignEdgeOut(BaseModel):
    from_node_id: int
    to_node_id: int


class CampaignMapOut(BaseModel):
    regions: list[CampaignRegionOut]
    edges: list[CampaignEdgeOut]
    focus_node_id: int | None
