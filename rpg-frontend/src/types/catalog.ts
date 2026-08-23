export type Rarity = "common" | "rare" | "epic" | "legendary";
export type EquipmentSlot = "weapon" | "helmet" | "armor" | "boots" | "gloves" | "ring" | "amulet";

export interface RaceOut {
  id: number;
  code: string;
  name: string;
  description: string | null;
  image_path: string | null;
}

export interface CharacterClassOut {
  id: number;
  code: string;
  name: string;
  description: string | null;
  image_path: string | null;
  base_hp: number;
  base_attack: number;
  base_defense: number;
  base_speed: number;
  base_crit_chance: number;
  base_crit_damage: number;
}

export interface HeroTemplateOut {
  id: number;
  name: string;
  description: string | null;
  image_path: string | null;
  race: RaceOut;
  character_class: CharacterClassOut;
}
