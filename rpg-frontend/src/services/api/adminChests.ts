import { api } from "./client";
import type { ChestCreate, ChestOut, ChestUpdate } from "@/types";

/** The only admin-write resource that exists on rpg-backend today — see
 * FRONTEND_API_MAP.md's admin section. Do not add sibling modules here for
 * heroes/enemies/items/etc. until the backend actually grows those
 * endpoints; the admin UI reads those via the regular public GET routes
 * instead, view-only. */

export async function getAllChestsAdmin(): Promise<ChestOut[]> {
  const { data } = await api.get<ChestOut[]>("/admin/chests");
  return data;
}

export async function createChest(payload: ChestCreate): Promise<ChestOut> {
  const { data } = await api.post<ChestOut>("/admin/chests", payload);
  return data;
}

export async function updateChest(id: number, payload: ChestUpdate): Promise<ChestOut> {
  const { data } = await api.put<ChestOut>(`/admin/chests/${id}`, payload);
  return data;
}

export async function toggleChestActive(id: number): Promise<ChestOut> {
  const { data } = await api.post<ChestOut>(`/admin/chests/${id}/toggle-active`);
  return data;
}
