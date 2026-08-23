import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { expeditionsApi } from "@/services/api";

export function useExpeditions() {
  return useQuery({ queryKey: ["expeditions"], queryFn: expeditionsApi.getExpeditions });
}

/** Polls while any expedition is still `running` — the same "no push,
 * client polls" pattern as Arena (see ARCHITECTURE.md's Stage 7 sweep
 * note): a running expedition becomes `completed` purely by time passing,
 * and nothing but a client re-checking ever notices that transition. */
export function useExpeditionHistory() {
  return useQuery({
    queryKey: ["expeditions", "history"],
    queryFn: expeditionsApi.getExpeditionHistory,
    refetchInterval: (query) => (query.state.data?.some((e) => e.status === "running") ? 5000 : false),
  });
}

function useInvalidateExpeditions() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["expeditions"] });
    queryClient.invalidateQueries({ queryKey: ["session"] });
    queryClient.invalidateQueries({ queryKey: ["profile"] });
  };
}

export function useStartExpedition() {
  const invalidate = useInvalidateExpeditions();
  return useMutation({
    mutationFn: expeditionsApi.startExpedition,
    onSuccess: invalidate,
  });
}

export function useClaimExpedition() {
  const invalidate = useInvalidateExpeditions();
  return useMutation({
    mutationFn: expeditionsApi.claimExpedition,
    onSuccess: invalidate,
  });
}
