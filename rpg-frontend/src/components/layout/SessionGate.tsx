import type { ReactNode } from "react";

import { CharacterCreationScreen } from "@/components/onboarding/CharacterCreationScreen";
import { ErrorState, Skeleton } from "@/components/ui";
import { useSession } from "@/hooks/useSession";

/** Runs the one POST /auth/session call for the whole app, exactly once,
 * regardless of which route the user lands on first — this is what makes
 * `useAuthStore`'s `isReady`/`user` reliable for any page (e.g. ProfilePage
 * depends on it without calling useSession itself). Pages that also need
 * the hero payload still call useSession() themselves; TanStack Query
 * serves that from cache (staleTime: Infinity) rather than re-fetching.
 *
 * Also the mandatory character-creation gate: a brand-new player has no
 * active_hero yet, and every route (including the bottom nav itself) lives
 * inside `children` here — rendering CharacterCreationScreen instead is
 * what makes onboarding unavoidable rather than just the default landing
 * page. Once creation succeeds it invalidates ["session"], this refetches,
 * and children render normally from then on. */
export function SessionGate({ children }: { children: ReactNode }) {
  const session = useSession();

  if (session.isPending) {
    return (
      <div className="flex h-dvh flex-col items-center justify-center gap-3 bg-bg-base p-6">
        <Skeleton className="h-14 w-14 rounded-full" />
        <Skeleton className="h-3 w-32" />
      </div>
    );
  }

  if (session.isError) {
    return (
      <div className="flex h-dvh items-center justify-center bg-bg-base p-6">
        <ErrorState error={session.error} onRetry={() => session.refetch()} />
      </div>
    );
  }

  if (!session.data.user.active_hero) {
    return <CharacterCreationScreen />;
  }

  return <>{children}</>;
}
