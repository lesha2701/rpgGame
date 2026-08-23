import { api } from "./client";
import type { SessionResponse, UserMeOut } from "@/types";

export async function startSession(): Promise<SessionResponse> {
  const { data } = await api.post<SessionResponse>("/auth/session");
  return data;
}

export async function getMe(): Promise<UserMeOut> {
  const { data } = await api.get<UserMeOut>("/auth/me");
  return data;
}
