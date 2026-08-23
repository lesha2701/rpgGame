import { api } from "./client";
import type { BattleOut, StartBattleRequest } from "@/types";

export async function startBattle(payload: StartBattleRequest): Promise<BattleOut> {
  const { data } = await api.post<BattleOut>("/battles", payload);
  return data;
}

export async function getBattles(): Promise<BattleOut[]> {
  const { data } = await api.get<BattleOut[]>("/battles");
  return data;
}

export async function getBattle(id: number): Promise<BattleOut> {
  const { data } = await api.get<BattleOut>(`/battles/${id}`);
  return data;
}
