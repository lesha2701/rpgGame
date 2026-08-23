import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { authApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";

/** Runs POST /auth/session once on app load — establishes/refreshes the
 * user row and returns the current UserMeOut (including active_hero), which
 * Home/Hero/Profile all read from rather than issuing their own /heroes/me
 * call redundantly. */
export function useSession() {
  const setUser = useAuthStore((s) => s.setUser);
  const setAdminToken = useAuthStore((s) => s.setAdminToken);
  const setReady = useAuthStore((s) => s.setReady);

  const query = useQuery({
    queryKey: ["session"],
    // The bot's /invite deep link opens the Mini App at .../?ref=<telegram_id>
    // (see rpg-bot/keyboards.py) — Telegram's WebView loads that URL as-is,
    // so window.location.search already has it by the time this runs, same
    // mechanism the football frontend uses (App.tsx's own createSession call).
    queryFn: () => authApi.startSession(new URLSearchParams(window.location.search).get("ref") ?? undefined),
    staleTime: Infinity,
    retry: 1,
  });

  useEffect(() => {
    if (query.data) {
      setUser(query.data.user);
      setAdminToken(query.data.admin_token);
      setReady(true);
    }
  }, [query.data, setUser, setAdminToken, setReady]);

  useEffect(() => {
    if (query.isError) setReady(true);
  }, [query.isError, setReady]);

  return query;
}
