import { api } from "./client";
import type { AdminUserDetailOut, AdminUserListOut, AdminUserStatsOut, AdminUserSummaryOut } from "@/types";

export async function listUsers(search: string, limit: number, offset: number): Promise<AdminUserListOut> {
  const { data } = await api.get<AdminUserListOut>("/admin/users", { params: { search: search || undefined, limit, offset } });
  return data;
}

export async function getUserStats(): Promise<AdminUserStatsOut> {
  const { data } = await api.get<AdminUserStatsOut>("/admin/users/stats");
  return data;
}

export async function getUserDetail(id: number): Promise<AdminUserDetailOut> {
  const { data } = await api.get<AdminUserDetailOut>(`/admin/users/${id}`);
  return data;
}

export async function grantCoins(id: number, amount: number, description: string): Promise<AdminUserSummaryOut> {
  const { data } = await api.post<AdminUserSummaryOut>(`/admin/users/${id}/grant-coins`, { amount, description });
  return data;
}

export async function deductCoins(id: number, amount: number, description: string): Promise<AdminUserSummaryOut> {
  const { data } = await api.post<AdminUserSummaryOut>(`/admin/users/${id}/deduct-coins`, { amount, description });
  return data;
}

export async function toggleBan(id: number): Promise<AdminUserSummaryOut> {
  const { data } = await api.post<AdminUserSummaryOut>(`/admin/users/${id}/toggle-ban`);
  return data;
}
