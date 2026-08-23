import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { arenaApi } from "@/services/api";
import type { ArenaActionRequest } from "@/types";

export function useMatches() {
  return useQuery({ queryKey: ["arena", "matches"], queryFn: arenaApi.getMatches });
}

/** Polls while the match is still running and it's genuinely worth
 * checking (matches Stage 9's own design: no push updates exist, the
 * client is expected to poll while waiting on the opponent — see
 * ARCHITECTURE.md's Stage 9 section). Stops polling once finished. */
export function useMatch(id: number) {
  return useQuery({
    queryKey: ["arena", "matches", id],
    queryFn: () => arenaApi.getMatch(id),
    refetchInterval: (query) => (query.state.data?.status === "running" ? 4000 : false),
  });
}

export function useCreateMatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: arenaApi.createMatch,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["arena", "matches"] }),
  });
}

export function useSubmitAction(matchId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ArenaActionRequest) => arenaApi.submitAction(matchId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["arena", "matches"] });
      queryClient.invalidateQueries({ queryKey: ["session"] });
    },
  });
}
