import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { campaignApi } from "@/services/api";
import type { CampaignActionRequest } from "@/types";

export function useCampaignMap() {
  return useQuery({ queryKey: ["campaign", "map"], queryFn: campaignApi.getCampaignMap });
}

export function useCampaignBattle(id: number) {
  return useQuery({
    queryKey: ["campaign", "battles", id],
    queryFn: () => campaignApi.getCampaignBattle(id),
    enabled: Number.isFinite(id),
  });
}

export function useStartCampaignBattle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: campaignApi.startCampaignBattle,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaign", "map"] });
    },
  });
}

/** Unlike Arena, there's no second player to wait on — the round resolves
 * fully within this one POST, so the response IS the next state. Written
 * straight into the query cache (not just invalidated) so the battle
 * screen updates instantly without a refetch round-trip. */
export function useSubmitCampaignAction(battleId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CampaignActionRequest) => campaignApi.submitCampaignAction(battleId, payload),
    onSuccess: (data) => {
      queryClient.setQueryData(["campaign", "battles", battleId], data);
      queryClient.invalidateQueries({ queryKey: ["session"] });
      if (data.status === "finished") {
        queryClient.invalidateQueries({ queryKey: ["campaign", "map"] });
      }
    },
  });
}
