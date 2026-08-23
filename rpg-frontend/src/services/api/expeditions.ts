import { api } from "./client";
import type { ExpeditionTemplateOut, UserExpeditionOut } from "@/types";

export async function getExpeditions(): Promise<ExpeditionTemplateOut[]> {
  const { data } = await api.get<ExpeditionTemplateOut[]>("/expeditions");
  return data;
}

export async function getExpedition(id: number): Promise<ExpeditionTemplateOut> {
  const { data } = await api.get<ExpeditionTemplateOut>(`/expeditions/${id}`);
  return data;
}

export async function getExpeditionHistory(): Promise<UserExpeditionOut[]> {
  const { data } = await api.get<UserExpeditionOut[]>("/expeditions/history");
  return data;
}

export async function startExpedition(templateId: number): Promise<UserExpeditionOut> {
  const { data } = await api.post<UserExpeditionOut>(`/expeditions/${templateId}/start`);
  return data;
}

export async function claimExpedition(userExpeditionId: number): Promise<UserExpeditionOut> {
  const { data } = await api.post<UserExpeditionOut>(`/expeditions/${userExpeditionId}/claim`);
  return data;
}
