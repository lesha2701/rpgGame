import axios, { AxiosError } from "axios";

import { getRawInitData, isInsideTelegram } from "@/lib/telegram";
import { useAuthStore } from "@/store/authStore";
import type { ApiError } from "@/types";

const API_URL = import.meta.env.VITE_API_URL ?? "/api/v1";

export const api = axios.create({ baseURL: API_URL });

api.interceptors.request.use((config) => {
  if (isInsideTelegram()) {
    config.headers.set("X-Telegram-Init-Data", getRawInitData());
  } else {
    // Dev-only fallback — the backend only honors this when RPG_DEV_MODE=true
    // (see rpg-backend/app/core/dependencies.py); it's a no-op/401 otherwise.
    config.headers.set("X-Dev-Mode", "true");
  }

  // Admin endpoints authenticate via bearer JWT instead — see
  // rpg-backend's core/dependencies.get_current_admin, matching the
  // football frontend's identical lib/api.ts pattern.
  if (config.url?.startsWith("/admin")) {
    const token = useAuthStore.getState().adminToken;
    if (token) config.headers.set("Authorization", `Bearer ${token}`);
  }

  return config;
});

export class ApiRequestError extends Error {
  code: string;
  status?: number;
  details?: Record<string, unknown>;

  constructor(message: string, code: string, status?: number, details?: Record<string, unknown>) {
    super(message);
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    const body = error.response?.data;
    if (body?.error) {
      throw new ApiRequestError(body.error.message, body.error.code, error.response?.status, body.error.details);
    }
    throw new ApiRequestError(error.message, "network_error", error.response?.status);
  },
);
