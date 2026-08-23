import type { EquipmentSlot, Rarity } from "./catalog";

// Mirrors rpg-backend's app/schemas/admin.py exactly — these are separate
// from the public Out types (types/catalog.ts, enemy.ts, item.ts, ...)
// because the backend itself keeps them separate: the public schemas
// deliberately omit is_active/sort_order, admin needs both.

export interface RaceAdminOut {
  id: number;
  code: string;
  name: string;
  description: string | null;
  image_path: string | null;
  is_active: boolean;
  sort_order: number;
}

export interface CharacterClassAdminOut {
  id: number;
  code: string;
  name: string;
  description: string | null;
  image_path: string | null;
  is_active: boolean;
  sort_order: number;
  base_hp: number;
  base_attack: number;
  base_defense: number;
  base_speed: number;
  base_crit_chance: number;
  base_crit_damage: number;
  hp_per_level: number;
  attack_per_level: number;
  defense_per_level: number;
  speed_per_level: number;
}

export interface HeroTemplateAdminOut {
  id: number;
  race_id: number;
  class_id: number;
  name: string;
  description: string | null;
  image_path: string | null;
  is_active: boolean;
  sort_order: number;
  race: RaceAdminOut;
  character_class: CharacterClassAdminOut;
}

export interface EnemyTemplateAdminOut {
  id: number;
  name: string;
  description: string | null;
  image_path: string | null;
  level: number;
  hp: number;
  attack: number;
  defense: number;
  speed: number;
  crit_chance: number;
  crit_damage: number;
  reward_xp: number;
  reward_coins: number;
  is_active: boolean;
  sort_order: number;
}

export interface ItemAffixAdminOut {
  id: number;
  stat_type: string;
}

export interface ItemTemplateAdminOut {
  id: number;
  slot: EquipmentSlot;
  tier: number;
  rarity: Rarity;
  name: string;
  description: string | null;
  image_path: string | null;
  is_active: boolean;
  sort_order: number;
  affixes: ItemAffixAdminOut[];
}

export interface ExpeditionTemplateAdminOut {
  id: number;
  name: string;
  description: string | null;
  duration_seconds: number;
  required_hero_level: number;
  reward_xp: number;
  reward_coins: number;
  is_active: boolean;
  sort_order: number;
}

export interface QuestDefinitionAdminOut {
  id: number;
  code: string;
  name: string;
  description: string | null;
  condition_type: string;
  target_value: number;
  reward_xp: number;
  reward_coins: number;
  is_active: boolean;
  sort_order: number;
}
