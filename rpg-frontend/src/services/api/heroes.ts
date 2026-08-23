import { api } from "./client";
import type { UserHeroOut } from "@/types";

export async function getMyHero(): Promise<UserHeroOut> {
  const { data } = await api.get<UserHeroOut>("/heroes/me");
  return data;
}

export async function createHero(hero_template_id: number, name: string): Promise<UserHeroOut> {
  const { data } = await api.post<UserHeroOut>("/heroes", { hero_template_id, name });
  return data;
}
