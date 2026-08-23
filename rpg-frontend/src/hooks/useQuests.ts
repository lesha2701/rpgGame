import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { questsApi } from "@/services/api";

export function useQuests() {
  return useQuery({ queryKey: ["quests"], queryFn: questsApi.getQuests });
}

export function useClaimQuest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: questsApi.claimQuest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quests"] });
      queryClient.invalidateQueries({ queryKey: ["session"] });
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}
