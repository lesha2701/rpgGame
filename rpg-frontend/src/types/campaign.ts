import type { BattleLogEntryOut } from "./battle";

export interface CampaignSkillOut {
  skill_definition_id: number;
  name: string;
  skill_type: string;
  cooldown_turns: number;
  cooldown_remaining: number;
  is_interrupt: boolean;
}

export interface CampaignHeroStateOut {
  current_hp: number;
  max_hp: number;
  attack_bonus: number;
  buff_turns_remaining: number;
  defense_bonus: number;
  defense_buff_turns_remaining: number;
  shield_remaining: number;
  stunned: boolean;
  dot_turns_remaining: number;
  skills: CampaignSkillOut[];
}

export interface CampaignEnemyIntentOut {
  ability_code: string | null;
  name: string;
  skill_type: string;
  status_label: string | null;
  min_damage: number | null;
  max_damage: number | null;
}

export interface CampaignEnemyStateOut {
  enemy_template_id: number;
  name: string;
  image_path: string | null;
  level: number;
  is_boss: boolean;
  current_hp: number;
  max_hp: number;
  shield_remaining: number;
  stunned: boolean;
  dot_turns_remaining: number;
  phase_order: number | null;
  intent: CampaignEnemyIntentOut | null;
}

export interface CampaignBattleOut {
  id: number;
  node_id: number;
  status: "running" | "finished";
  current_round: number;
  hero: CampaignHeroStateOut;
  enemy: CampaignEnemyStateOut;
  log: BattleLogEntryOut[];
  result: "won" | "lost" | null;
  reward_xp: number;
  reward_coins: number;
  is_first_clear: boolean;
  created_at: string;
  finished_at: string | null;
}

export interface StartCampaignBattleRequest {
  node_id: number;
}

export interface CampaignActionRequest {
  round: number;
  action_type: "basic_attack" | "skill" | "defend";
  skill_id?: number | null;
}

export type CampaignNodeType = "battle" | "elite" | "boss" | "story_event" | "treasure" | "merchant" | "rest";

export interface CampaignNodeOut {
  id: number;
  region_id: number;
  code: string;
  name: string;
  node_type: CampaignNodeType;
  enemy_template_id: number | null;
  enemy_name: string | null;
  enemy_image_path: string | null;
  enemy_level: number | null;
  level: number;
  depth: number;
  sort_order: number;
  completed: boolean;
  available: boolean;
  is_current: boolean;
  clear_count: number;
}

export interface CampaignRegionOut {
  id: number;
  code: string;
  name: string;
  description: string | null;
  image_path: string | null;
  sort_order: number;
  nodes: CampaignNodeOut[];
}

export interface CampaignEdgeOut {
  from_node_id: number;
  to_node_id: number;
}

export interface CampaignMapOut {
  regions: CampaignRegionOut[];
  edges: CampaignEdgeOut[];
  focus_node_id: number | null;
}
