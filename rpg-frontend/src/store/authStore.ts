import { create } from "zustand";

import type { UserMeOut } from "@/types";

interface AuthState {
  user: UserMeOut | null;
  /** Non-null only when the backend's own /auth/session response included
   * one — that's the sole "is this user an admin" signal available
   * (UserMeOut itself carries no is_admin field), matching the football
   * frontend's identical pattern. */
  adminToken: string | null;
  isReady: boolean;
  setUser: (user: UserMeOut) => void;
  setAdminToken: (token: string | null) => void;
  setReady: (ready: boolean) => void;
  reset: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  adminToken: null,
  isReady: false,
  setUser: (user) => set({ user }),
  setAdminToken: (adminToken) => set({ adminToken }),
  setReady: (isReady) => set({ isReady }),
  reset: () => set({ user: null, adminToken: null, isReady: false }),
}));
