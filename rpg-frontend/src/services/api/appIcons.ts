import { api } from "./client";
import type { AppIconOut } from "@/types";

export async function getAppIcons(): Promise<AppIconOut[]> {
  const { data } = await api.get<AppIconOut[]>("/app-icons");
  return data;
}
