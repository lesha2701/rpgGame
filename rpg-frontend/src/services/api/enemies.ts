import { api } from "./client";
import type { EnemyOut } from "@/types";

export async function getEnemies(): Promise<EnemyOut[]> {
  const { data } = await api.get<EnemyOut[]>("/enemies");
  return data;
}

export async function getEnemy(id: number): Promise<EnemyOut> {
  const { data } = await api.get<EnemyOut>(`/enemies/${id}`);
  return data;
}
