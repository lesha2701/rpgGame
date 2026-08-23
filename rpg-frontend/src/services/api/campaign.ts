import { api } from "./client";
import type { CampaignActionRequest, CampaignBattleOut, CampaignMapOut, StartCampaignBattleRequest } from "@/types";

export async function getCampaignMap(): Promise<CampaignMapOut> {
  const { data } = await api.get<CampaignMapOut>("/campaign/map");
  return data;
}

export async function startCampaignBattle(payload: StartCampaignBattleRequest): Promise<CampaignBattleOut> {
  const { data } = await api.post<CampaignBattleOut>("/campaign/battles", payload);
  return data;
}

export async function getCampaignBattle(id: number): Promise<CampaignBattleOut> {
  const { data } = await api.get<CampaignBattleOut>(`/campaign/battles/${id}`);
  return data;
}

export async function submitCampaignAction(id: number, payload: CampaignActionRequest): Promise<CampaignBattleOut> {
  const { data } = await api.post<CampaignBattleOut>(`/campaign/battles/${id}/action`, payload);
  return data;
}
