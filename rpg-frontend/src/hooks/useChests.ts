import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { chestsApi } from "@/services/api";

export function useChests() {
  return useQuery({ queryKey: ["chests"], queryFn: chestsApi.getChests });
}

export function useChest(id: number) {
  return useQuery({ queryKey: ["chests", id], queryFn: () => chestsApi.getChest(id) });
}

export function useFreeChestStatus() {
  return useQuery({ queryKey: ["chests", "free"], queryFn: chestsApi.getFreeChestStatus });
}

function useInvalidateAfterOpen() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["inventory"] });
    queryClient.invalidateQueries({ queryKey: ["profile"] });
    queryClient.invalidateQueries({ queryKey: ["chests", "free"] });
  };
}

export function useOpenChest() {
  const invalidate = useInvalidateAfterOpen();
  return useMutation({
    mutationFn: (chestId: number) => chestsApi.openChest(chestId),
    onSuccess: invalidate,
  });
}

export function useClaimFreeChest() {
  const invalidate = useInvalidateAfterOpen();
  return useMutation({
    mutationFn: chestsApi.claimFreeChest,
    onSuccess: invalidate,
  });
}
