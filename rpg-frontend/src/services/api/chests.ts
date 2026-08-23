import { api } from "./client";
import type { ChestOpeningHistoryOut, ChestOpenResult, ChestOut, FreeChestStatusOut } from "@/types";

export async function getChests(): Promise<ChestOut[]> {
  const { data } = await api.get<ChestOut[]>("/chests");
  return data;
}

export async function getChest(id: number): Promise<ChestOut> {
  const { data } = await api.get<ChestOut>(`/chests/${id}`);
  return data;
}

export async function openChest(id: number, idempotency_key?: string): Promise<ChestOpenResult> {
  const { data } = await api.post<ChestOpenResult>(`/chests/${id}/open`, { idempotency_key });
  return data;
}

export async function getFreeChestStatus(): Promise<FreeChestStatusOut> {
  const { data } = await api.get<FreeChestStatusOut>("/chests/free");
  return data;
}

export async function claimFreeChest(): Promise<ChestOpenResult> {
  const { data } = await api.post<ChestOpenResult>("/chests/free/claim");
  return data;
}

export async function getChestOpeningHistory(): Promise<ChestOpeningHistoryOut[]> {
  const { data } = await api.get<ChestOpeningHistoryOut[]>("/chests/openings");
  return data;
}
