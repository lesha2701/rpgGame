import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { adminChestsApi } from "@/services/api";
import type { ChestCreate, ChestUpdate } from "@/types";

export function useAdminChests() {
  return useQuery({ queryKey: ["admin", "chests"], queryFn: adminChestsApi.getAllChestsAdmin });
}

function useInvalidateAdminChests() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["admin", "chests"] });
}

export function useCreateChest() {
  const invalidate = useInvalidateAdminChests();
  return useMutation({
    mutationFn: (payload: ChestCreate) => adminChestsApi.createChest(payload),
    onSuccess: invalidate,
  });
}

export function useUpdateChest() {
  const invalidate = useInvalidateAdminChests();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ChestUpdate }) => adminChestsApi.updateChest(id, payload),
    onSuccess: invalidate,
  });
}

export function useToggleChestActive() {
  const invalidate = useInvalidateAdminChests();
  return useMutation({
    mutationFn: adminChestsApi.toggleChestActive,
    onSuccess: invalidate,
  });
}
