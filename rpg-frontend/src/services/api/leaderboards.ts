import { api } from "./client";
import type { LeaderboardOut, LeaderboardType } from "@/types";

export async function getLeaderboard(
  type: LeaderboardType,
  limit = 20,
  offset = 0,
): Promise<LeaderboardOut> {
  const { data } = await api.get<LeaderboardOut>(`/leaderboards/${type}`, { params: { limit, offset } });
  return data;
}
