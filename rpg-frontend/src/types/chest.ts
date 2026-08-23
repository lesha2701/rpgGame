import type { Rarity } from "./catalog";
import type { ItemAffixOut, ItemStatsOut } from "./item";

export interface ChestRarityProbabilityOut {
  rarity: Rarity;
  probability: number;
}

export interface ChestOut {
  id: number;
  slug: string;
  name: string;
  description: string;
  price: number;
  image_path: string | null;
  guaranteed_min_rarity: Rarity | null;
  is_active: boolean;
  rarity_probabilities: ChestRarityProbabilityOut[];
}

export interface ChestSummaryOut {
  id: number;
  name: string;
}

export interface ChestRewardOut {
  item_id: number;
  item_template_id: number;
  name: string;
  slot: string;
  tier: number;
  rarity: Rarity;
  image_path: string | null;
  stats: ItemStatsOut;
  affixes: ItemAffixOut[];
}

export interface ChestOpenResult {
  opening_id: number;
  chest: ChestSummaryOut;
  reward: ChestRewardOut;
  balance: number;
}

export interface FreeChestStatusOut {
  chest: ChestOut;
  is_available: boolean;
  next_available_at: string | null;
}

export interface ChestOpeningHistoryOut {
  id: number;
  chest: ChestSummaryOut;
  reward_item_id: number;
  reward_item_name: string;
  reward_rarity: Rarity;
  price_paid: number;
  created_at: string;
}

// --- admin CRUD (rpg-backend's admin_chests.py — the only admin-write
// resource that exists today; see FRONTEND_API_MAP.md) ---------------------

export interface ChestRarityProbabilityIn {
  rarity: Rarity;
  probability: number;
}

export interface ChestCreate {
  slug: string;
  name: string;
  description?: string;
  price: number;
  image_path?: string | null;
  guaranteed_min_rarity?: Rarity | null;
  is_active?: boolean;
  sort_order?: number;
  rarity_probabilities: ChestRarityProbabilityIn[];
}

export interface ChestUpdate {
  name?: string;
  description?: string;
  price?: number;
  image_path?: string | null;
  guaranteed_min_rarity?: Rarity | null;
  is_active?: boolean;
  sort_order?: number;
  rarity_probabilities?: ChestRarityProbabilityIn[];
}
