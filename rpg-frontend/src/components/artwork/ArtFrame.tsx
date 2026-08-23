import { useState } from "react";

import type { Rarity } from "@/types";
import { RARITY_RING_CLASS } from "./rarity";
import { RarityCorners } from "./RarityCorners";

export type ArtworkSize = "thumbnail" | "card" | "portrait" | "battle" | "detail" | "full-bleed";
/** Color temperature for the empty-state wash — matches the confirmed
 * Ember & Iron per-context accents (ember for heroes/home, crimson for
 * enemies, frost for bestiary, epic-wash for a violet/arena-adjacent tone). */
export type ArtworkVariant = "ember" | "enemy" | "frost" | "epic-wash";

const SIZE_CLASS: Record<ArtworkSize, string> = {
  thumbnail: "aspect-square rounded-md",
  card: "aspect-[3/4] rounded-lg",
  portrait: "aspect-[3/4] rounded-xl",
  battle: "h-32 rounded-lg",
  detail: "aspect-[3/4] rounded-2xl",
  "full-bleed": "absolute inset-0 rounded-none",
};

const VARIANT_WASH: Record<ArtworkVariant, string> = {
  ember:
    "bg-[radial-gradient(circle_at_32%_24%,rgba(224,138,76,0.24),transparent_55%),radial-gradient(circle_at_72%_70%,rgba(122,62,26,0.3),transparent_60%),linear-gradient(165deg,#2A2119_0%,#171310_100%)]",
  enemy:
    "bg-[radial-gradient(circle_at_70%_26%,rgba(177,68,52,0.26),transparent_55%),radial-gradient(circle_at_28%_72%,rgba(92,40,30,0.3),transparent_60%),linear-gradient(165deg,#241713_0%,#140D0B_100%)]",
  frost:
    "bg-[radial-gradient(circle_at_60%_26%,rgba(92,139,148,0.24),transparent_55%),linear-gradient(165deg,#1B2423_0%,#0F1413_100%)]",
  "epic-wash":
    "bg-[radial-gradient(circle_at_55%_30%,rgba(155,95,192,0.24),transparent_55%),linear-gradient(165deg,#241C2C_0%,#141018_100%)]",
};

export interface ArtFrameProps {
  /** Real artwork URL. Always optional — Stage 12's artwork pipeline
   * doesn't exist yet, so this is legitimately undefined for every hero/
   * enemy/item/chest today. Never pass a fabricated placeholder image URL
   * here; the empty-state wash below IS the correct rendering of "no
   * artwork yet." */
  src?: string | null;
  alt: string;
  size?: ArtworkSize;
  variant?: ArtworkVariant;
  rarity?: Rarity;
  /** Explicit state override. Defaults to derived from `src` + internal
   * <img> load result — pass "loading" while a request that WILL populate
   * `src` is still in flight (skeleton), "error" if a known-bad URL should
   * fall back visibly instead of rendering broken. */
  state?: "loading" | "error";
  /** Shown only in the empty state — used by Hero/Home, where the product
   * decision is "the user uploads their own photo," so the empty state
   * should say so. Omit everywhere else (enemy/item/chest empty states are
   * silent washes, no call-to-action copy). */
  emptyHint?: string;
  className?: string;
}

export function ArtFrame({
  src,
  alt,
  size = "card",
  variant = "ember",
  rarity,
  state,
  emptyHint,
  className = "",
}: ArtFrameProps) {
  const [loadFailed, setLoadFailed] = useState(false);

  const effectiveState = state ?? (src && !loadFailed ? "loaded" : loadFailed ? "error" : "empty");
  const ringClass = rarity ? RARITY_RING_CLASS[rarity] : "ring-1 ring-hairline";

  // "full-bleed" already carries its own `absolute` from SIZE_CLASS — adding
  // `relative` here too would fight it for the position property (both are
  // single-property utilities of equal specificity, so Tailwind's internal
  // stylesheet order decides the winner, not the order of classes in JSX).
  const positionClass = size === "full-bleed" ? "" : "relative";

  return (
    <div className={`${positionClass} overflow-hidden bg-bg-raised ${SIZE_CLASS[size]} ${ringClass} ${className}`}>
      {effectiveState === "loading" && (
        <div className="absolute inset-0 animate-shimmer bg-[linear-gradient(90deg,transparent,rgba(243,237,228,0.06),transparent)] bg-[length:400px_100%] bg-bg-raised" />
      )}

      {effectiveState === "loaded" && src && (
        <img
          src={src}
          alt={alt}
          className="h-full w-full object-cover"
          onError={() => setLoadFailed(true)}
          loading="lazy"
        />
      )}

      {effectiveState === "error" && (
        <div className={`flex h-full w-full flex-col items-center justify-center gap-1 ${VARIANT_WASH[variant]}`}>
          <span className="text-lg opacity-40" aria-hidden>
            ⚠
          </span>
          <span className="px-2 text-center font-mono text-[9.5px] text-ink-dim">Не удалось загрузить</span>
        </div>
      )}

      {effectiveState === "empty" && (
        <div className={`flex h-full w-full flex-col items-center justify-center gap-2 ${VARIANT_WASH[variant]}`}>
          {emptyHint && (
            <>
              <span className="text-xl opacity-40" aria-hidden>
                🖼
              </span>
              <span className="px-3 text-center font-mono text-[9.5px] leading-snug text-ink-dim">{emptyHint}</span>
            </>
          )}
        </div>
      )}

      {rarity && <RarityCorners rarity={rarity} />}
    </div>
  );
}
