import type { HeroProgressOut } from "./common";

export interface QuestOut {
  id: number;
  code: string;
  name: string;
  description: string | null;
  condition_type: string;
  target_value: number;
  current_progress: number;
  is_completed: boolean;
  is_claimed: boolean;
  is_active_slot: boolean;
  reward_xp: number;
  reward_coins: number;
}

export interface QuestClaimOut {
  id: number;
  code: string;
  name: string;
  reward_xp: number;
  reward_coins: number;
  claimed_at: string;
  hero_progress: HeroProgressOut;
}
