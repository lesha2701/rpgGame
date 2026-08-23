import { api } from "./client";
import type { AvailableSkillsOut, CharacterSkillOut } from "@/types";

export async function getMySkills(): Promise<CharacterSkillOut[]> {
  const { data } = await api.get<CharacterSkillOut[]>("/heroes/me/skills");
  return data;
}

export async function getAvailableSkills(): Promise<AvailableSkillsOut> {
  const { data } = await api.get<AvailableSkillsOut>("/heroes/me/skills/available");
  return data;
}

export async function upgradeSkill(skillDefinitionId: number): Promise<CharacterSkillOut> {
  const { data } = await api.post<CharacterSkillOut>(`/heroes/me/skills/${skillDefinitionId}/upgrade`);
  return data;
}
