export interface SkillDefinitionOut {
  id: number;
  code: string;
  name: string;
  description: string | null;
  skill_type: string;
  base_power: number;
  power_per_skill_level: number;
  cooldown_turns: number;
  required_hero_level: number;
}

export interface CharacterSkillOut {
  id: number;
  level: number;
  power: number;
  skill_definition: SkillDefinitionOut;
}

export interface AvailableSkillOut {
  skill_definition: SkillDefinitionOut;
  is_unlocked: boolean;
  current_level: number;
  is_max_level: boolean;
  next_upgrade_cost: number | null;
}

export interface SkillBudgetOut {
  total: number;
  spent: number;
  available: number;
}

export interface AvailableSkillsOut {
  budget: SkillBudgetOut;
  skills: AvailableSkillOut[];
}
