export interface ExpeditionTemplateOut {
  id: number;
  name: string;
  description: string | null;
  image_path: string | null;
  duration_seconds: number;
  required_hero_level: number;
  reward_xp: number;
  reward_coins: number;
  is_active: boolean;
  is_available_to_user: boolean;
}

export interface ExpeditionSummaryOut {
  id: number;
  name: string;
}

export interface UserExpeditionOut {
  id: number;
  expedition: ExpeditionSummaryOut;
  status: "running" | "completed" | "claimed";
  started_at: string;
  completed_at: string;
  claimed_at: string | null;
  reward_xp: number;
  reward_coins: number;
  hero_level: number;
  hero_xp: number;
  balance: number;
}
