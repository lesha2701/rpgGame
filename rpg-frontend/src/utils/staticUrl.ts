/** Resolves a backend-relative image_path (e.g. "enemies/goblin_a1b2.png")
 * into a real, loadable URL. Relative on purpose — the dev proxy (and, in
 * production, whatever reverse-proxies /static the same way it does /api)
 * means this never needs an absolute backend origin baked in at build
 * time. Mirrors the football frontend's own staticUrl() helper. */
export function staticUrl(path: string | null | undefined): string | undefined {
  if (!path) return undefined;
  return `/static/${path}`;
}
