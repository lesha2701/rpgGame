import { useQuery } from "@tanstack/react-query";

import { enemiesApi } from "@/services/api";

export function useEnemies() {
  return useQuery({ queryKey: ["enemies"], queryFn: enemiesApi.getEnemies });
}

export function useEnemy(id: number) {
  return useQuery({ queryKey: ["enemies", id], queryFn: () => enemiesApi.getEnemy(id) });
}
