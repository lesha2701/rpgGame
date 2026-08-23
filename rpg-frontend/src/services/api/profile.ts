import { api } from "./client";
import type { ProfileOut, PublicProfileOut } from "@/types";

export async function getMyProfile(): Promise<ProfileOut> {
  const { data } = await api.get<ProfileOut>("/profile/me");
  return data;
}

export async function getPublicProfile(userId: number): Promise<PublicProfileOut> {
  const { data } = await api.get<PublicProfileOut>(`/profile/${userId}`);
  return data;
}
