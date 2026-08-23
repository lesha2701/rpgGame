import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { inventoryApi } from "@/services/api";

export function useInventory() {
  return useQuery({ queryKey: ["inventory"], queryFn: inventoryApi.getInventory });
}

export function useEquipment() {
  return useQuery({ queryKey: ["equipment"], queryFn: inventoryApi.getEquipment });
}

/** Both mutations invalidate inventory + equipment + the session (hero
 * stats change once equipment does) — cheap at this data volume, and keeps
 * every screen reading either of those in sync without manual patching. */
function useInvalidateAfterEquipChange() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["inventory"] });
    queryClient.invalidateQueries({ queryKey: ["equipment"] });
    queryClient.invalidateQueries({ queryKey: ["session"] });
  };
}

export function useEquipItem() {
  const invalidate = useInvalidateAfterEquipChange();
  return useMutation({
    mutationFn: inventoryApi.equipItem,
    onSuccess: invalidate,
  });
}

export function useUnequipItem() {
  const invalidate = useInvalidateAfterEquipChange();
  return useMutation({
    mutationFn: inventoryApi.unequipItem,
    onSuccess: invalidate,
  });
}
