import { api } from "./client";
import type { EquippedItemsOut, UserItemOut } from "@/types";

export async function getInventory(): Promise<UserItemOut[]> {
  const { data } = await api.get<UserItemOut[]>("/heroes/me/inventory");
  return data;
}

export async function getInventoryItem(id: number): Promise<UserItemOut> {
  const { data } = await api.get<UserItemOut>(`/heroes/me/inventory/${id}`);
  return data;
}

export async function getEquipment(): Promise<EquippedItemsOut> {
  const { data } = await api.get<EquippedItemsOut>("/heroes/me/equipment");
  return data;
}

export async function equipItem(userItemId: number): Promise<UserItemOut> {
  const { data } = await api.post<UserItemOut>(`/heroes/me/equipment/${userItemId}/equip`);
  return data;
}

export async function unequipItem(userItemId: number): Promise<UserItemOut> {
  const { data } = await api.post<UserItemOut>(`/heroes/me/equipment/${userItemId}/unequip`);
  return data;
}
