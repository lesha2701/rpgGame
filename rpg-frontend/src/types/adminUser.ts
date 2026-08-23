import type { ProfileStatisticsOut } from "./profile";

export interface AdminUserSummaryOut {
  id: number;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  balance: number;
  is_admin: boolean;
  is_banned: boolean;
  created_at: string;
  hero_name: string | null;
  hero_level: number | null;
}

export interface AdminUserListOut {
  users: AdminUserSummaryOut[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminUserDetailOut extends AdminUserSummaryOut {
  statistics: ProfileStatisticsOut;
}

export interface AdminUserStatsOut {
  total_users: number;
  banned_users: number;
  admin_users: number;
  users_with_hero: number;
  total_balance_in_circulation: number;
}
