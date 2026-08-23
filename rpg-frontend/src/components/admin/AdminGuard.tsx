import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useSession } from "@/hooks/useSession";
import { useAuthStore } from "@/store/authStore";

/** Client-side UX gate only — the real security boundary is server-side
 * (rpg-backend's get_current_admin re-checks RPG_ADMIN_TELEGRAM_IDS on
 * every /admin/* request). Matches the football frontend's AdminGuard in
 * shape, adapted to RPG's session response (no `is_admin` field on the
 * user — presence of a non-null admin_token from /auth/session is the only
 * signal). Calls useSession() itself rather than relying on some other
 * page having done it first — admin routes aren't nested under the mobile
 * AppShell/SessionGate, so a deep link straight to /admin needs its own
 * bootstrap. */
export function AdminGuard({ children }: { children: ReactNode }) {
  const session = useSession();
  const isReady = useAuthStore((s) => s.isReady);
  const adminToken = useAuthStore((s) => s.adminToken);

  if (session.isPending || !isReady) {
    return <div className="flex h-dvh items-center justify-center bg-bg-base text-ink-dim">Загрузка...</div>;
  }

  if (!adminToken) return <Navigate to="/" replace />;

  return <>{children}</>;
}
