import { api } from "./client";
import type { CharacterClassOut, HeroTemplateOut, RaceOut } from "@/types";

export async function getRaces(): Promise<RaceOut[]> {
  const { data } = await api.get<RaceOut[]>("/races");
  return data;
}

export async function getClasses(): Promise<CharacterClassOut[]> {
  const { data } = await api.get<CharacterClassOut[]>("/classes");
  return data;
}

export async function getHeroTemplates(): Promise<HeroTemplateOut[]> {
  const { data } = await api.get<HeroTemplateOut[]>("/hero-templates");
  return data;
}
