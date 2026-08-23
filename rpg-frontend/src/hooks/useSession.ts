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
    queryFn: authApi.startSession,
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
