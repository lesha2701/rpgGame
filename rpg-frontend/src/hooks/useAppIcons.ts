import { useQuery } from "@tanstack/react-query";

import { appIconsApi } from "@/services/api";

/** One fetch, cached app-wide — every icon slot (bottom nav, Battle hub
 * rows, More page rows) reads from this same map instead of issuing its
 * own request. `staleTime: Infinity` matches useSession's own convention
 * for "rarely changes, fine to keep for the whole app session." */
export function useAppIcons() {
  return useQuery({
    queryKey: ["app-icons"],
    queryFn: appIconsApi.getAppIcons,
    staleTime: Infinity,
  });
}

/** Plain lookup, not a hook — named without the `use` prefix on purpose so
 * it's safe to call inside .map()/render-prop callbacks (a `use`-prefixed
 * name there would trip the rules-of-hooks lint rule for no reason, since
 * this touches no React hook internals). */
export function findAppIconPath(icons: { key: string; image_path: string | null }[] | undefined, key: string): string | null {
  return icons?.find((i) => i.key === key)?.image_path ?? null;
}
