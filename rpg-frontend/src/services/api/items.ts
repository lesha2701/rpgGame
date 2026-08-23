import { api } from "./client";
import type { ItemTemplateOut } from "@/types";

export async function getItemTemplates(): Promise<ItemTemplateOut[]> {
  const { data } = await api.get<ItemTemplateOut[]>("/item-templates");
  return data;
}
