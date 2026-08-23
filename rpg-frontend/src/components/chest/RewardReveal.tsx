import { ItemArtwork } from "@/components/artwork";
import { RARITY_LABEL, RARITY_TEXT_CLASS } from "@/components/artwork/rarity";
import type { ChestRewardOut, Rarity } from "@/types";

const RAYS = [0, 45, 90, 135, 180, 225, 270, 315];

const RARITY_CARD_CLASS: Record<Rarity, string> = {
  common: "border-hairline",
  rare: "border-rarity-rare shadow-glow-rare",
  epic: "border-rarity-epic shadow-glow-epic",
  legendary: "border-rarity-legendary shadow-glow-legendary animate-legendary-breathe",
};

const RARITY_GLOW: Record<Rarity, { outer: string; inner: string }> = {
  common: { outer: "rgba(139,132,120,0.28)", inner: "rgba(139,132,120,0.05)" },
  rare: { outer: "rgba(91,143,176,0.4)", inner: "rgba(91,143,176,0.08)" },
  epic: { outer: "rgba(155,95,192,0.4)", inner: "rgba(155,95,192,0.08)" },
  legendary: { outer: "rgba(232,162,61,0.4)", inner: "rgba(232,162,61,0.08)" },
};

/** Chest Opening's reveal state — breathing radial glow + static twinkling
 * rays, explicitly never a rotating/conic "radar" effect (rejected in the
 * Ember & Iron v3 design review), tinted and scaled by the actual reward
 * rarity so a legendary pull visibly outshines a common one instead of
 * every reveal getting the same fixed amber glow. The card's entrance is a
 * one-shot scale/opacity pop (animate-card-pop-in) — a finite transition,
 * not a loop, so it doesn't fight the "never spinning" rule either. */
export function RewardReveal({ reward }: { reward: ChestRewardOut }) {
  const showAmbientGlow = reward.rarity !== "common";

  return (
    <div className="relative flex flex-col items-center gap-4 py-10">
      <div
        className="pointer-events-none absolute left-1/2 top-16 h-64 w-64 -translate-x-1/2 -translate-y-1/2 animate-reveal-flash rounded-full bg-[radial-gradient(circle,rgba(243,237,228,0.5),transparent_70%)]"
        aria-hidden
      />

      {showAmbientGlow && (
        <>
          <div
            className="pointer-events-none absolute left-1/2 top-16 h-64 w-64 -translate-x-1/2 -translate-y-1/2 animate-reward-glow rounded-full"
            style={{
              background: `radial-gradient(circle, ${RARITY_GLOW[reward.rarity].outer}, ${RARITY_GLOW[reward.rarity].inner} 55%, transparent 75%)`,
            }}
          />
          <div className="pointer-events-none absolute left-1/2 top-16 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2">
            {RAYS.map((deg, i) => (
              <span
                key={deg}
                className={`absolute left-0 top-0 w-0.5 animate-ray-twinkle bg-gradient-to-b to-transparent ${
                  reward.rarity === "legendary" ? "from-rarity-legendary/60" : "from-rarity-epic/50"
                }`}
                style={{
                  height: i % 2 === 0 ? "60px" : "46px",
                  transform: `rotate(${deg}deg) translateY(-${i % 2 === 0 ? 65 : 51}px)`,
                  transformOrigin: "top center",
                  animationDelay: `${(i * 0.35).toFixed(2)}s`,
                }}
              />
            ))}
          </div>
        </>
      )}

      <div
        className={`relative z-10 w-[170px] animate-card-pop-in overflow-hidden rounded-lg border-2 bg-bg-surface ${RARITY_CARD_CLASS[reward.rarity]}`}
      >
        <ItemArtwork item={reward} size="card" className="rounded-none" />
        <div className="p-3 text-center">
          <p className={`font-display text-sm font-semibold ${RARITY_TEXT_CLASS[reward.rarity]}`}>{reward.name}</p>
          <p className="mt-0.5 font-mono text-[10px] uppercase tracking-wide text-ink-dim">
            {RARITY_LABEL[reward.rarity]} · T{reward.tier}
          </p>
        </div>
      </div>
    </div>
  );
}
