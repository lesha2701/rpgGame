import { api } from "./client";
import type { AppIconAdminOut } from "@/types";

export async function getAllAppIconsAdmin(): Promise<AppIconAdminOut[]> {
  const { data } = await api.get<AppIconAdminOut[]>("/admin/app-icons");
  return data;
}
