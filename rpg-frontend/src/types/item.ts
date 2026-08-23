import type { EquipmentSlot, Rarity } from "./catalog";

export interface ItemStatsOut {
  hp: number;
  attack: number;
  defense: number;
  speed: number;
}

export interface ItemAffixOut {
  id: number;
  stat_type: string;
}

export interface ItemTemplateOut {
  id: number;
  slot: EquipmentSlot;
  tier: number;
  rarity: Rarity;
  name: string;
  description: string | null;
  image_path: string | null;
  required_hero_level: number;
  stats: ItemStatsOut;
  affixes: ItemAffixOut[];
}

export interface UserItemOut {
  id: number;
  item_template: ItemTemplateOut;
  is_equipped: boolean;
  equipped_hero_id: number | null;
}

export type EquippedItemsOut = Partial<Record<EquipmentSlot, UserItemOut>>;
