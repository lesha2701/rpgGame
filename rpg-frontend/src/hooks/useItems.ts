import { useQuery } from "@tanstack/react-query";

import { itemsApi } from "@/services/api";

export function useItemTemplates() {
  return useQuery({ queryKey: ["item-templates"], queryFn: itemsApi.getItemTemplates });
}
