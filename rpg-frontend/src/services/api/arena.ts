import { api } from "./client";
import type { ArenaActionRequest, ArenaMatchOut, StartArenaMatchRequest } from "@/types";

export async function createMatch(payload: StartArenaMatchRequest): Promise<ArenaMatchOut> {
  const { data } = await api.post<ArenaMatchOut>("/arena/matches", payload);
  return data;
}

export async function getMatches(): Promise<ArenaMatchOut[]> {
  const { data } = await api.get<ArenaMatchOut[]>("/arena/matches");
  return data;
}

export async function getMatch(id: number): Promise<ArenaMatchOut> {
  const { data } = await api.get<ArenaMatchOut>(`/arena/matches/${id}`);
  return data;
}

export async function submitAction(id: number, payload: ArenaActionRequest): Promise<ArenaMatchOut> {
  const { data } = await api.post<ArenaMatchOut>(`/arena/matches/${id}/action`, payload);
  return data;
}
