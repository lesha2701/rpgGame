import type { UserHeroOut } from "./hero";

export interface UserMeOut {
  id: number;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  active_hero: UserHeroOut | null;
  referral_code: string;
  referral_count: number;
}

export interface SessionResponse {
  user: UserMeOut;
  admin_token: string | null;
}
