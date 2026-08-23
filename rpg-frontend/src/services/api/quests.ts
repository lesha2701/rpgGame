import { api } from "./client";
import type { QuestClaimOut, QuestOut } from "@/types";

export async function getQuests(): Promise<QuestOut[]> {
  const { data } = await api.get<QuestOut[]>("/quests");
  return data;
}

export async function claimQuest(userQuestId: number): Promise<QuestClaimOut> {
  const { data } = await api.post<QuestClaimOut>(`/quests/${userQuestId}/claim`);
  return data;
}
