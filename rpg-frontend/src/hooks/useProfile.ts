import { useQuery } from "@tanstack/react-query";

import { profileApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";

/** GET /profile/me — used by Home (balance pill) and ProfilePage (full
 * statistics). Shares one query cache entry across both, so navigating
 * Home → Profile doesn't re-fetch. */
export function useMyProfile() {
  const isReady = useAuthStore((s) => s.isReady);
  const hasUser = useAuthStore((s) => s.user !== null);

  return useQuery({
    queryKey: ["profile", "me"],
    queryFn: profileApi.getMyProfile,
    enabled: isReady && hasUser,
  });
}
