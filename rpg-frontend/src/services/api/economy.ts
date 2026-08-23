import { api } from "./client";
import type { WalletOut } from "@/types";

export async function getWallet(): Promise<WalletOut> {
  const { data } = await api.get<WalletOut>("/economy");
  return data;
}
