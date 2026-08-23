export type LeaderboardType = "level" | "pve_wins" | "arena_wins" | "coins";

export interface LeaderboardHeroOut {
  name: string;
  level: number;
}

export interface LeaderboardEntryOut {
  rank: number;
  user_id: number;
  username: string | null;
  hero: LeaderboardHeroOut | null;
  value: number;
}

export interface LeaderboardOut {
  type: string;
  entries: LeaderboardEntryOut[];
  total: number;
  limit: number;
  offset: number;
  my_rank: number | null;
  my_value: number;
}
