import { useQuery } from "@tanstack/react-query";

import { leaderboardsApi } from "@/services/api";
import type { LeaderboardType } from "@/types";

export function useLeaderboard(type: LeaderboardType, limit = 20, offset = 0) {
  return useQuery({
    queryKey: ["leaderboards", type, limit, offset],
    queryFn: () => leaderboardsApi.getLeaderboard(type, limit, offset),
  });
}
