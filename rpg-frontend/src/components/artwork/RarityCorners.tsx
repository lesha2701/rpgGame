import type { Rarity } from "@/types";
import { RARITY_HAS_CORNERS } from "./rarity";

const BORDER_COLOR: Record<Rarity, string> = {
  common: "border-rarity-common",
  rare: "border-rarity-rare",
  epic: "border-rarity-epic",
  legendary: "border-rarity-legendary",
};

/** Corner-bracket ornament for epic/legendary artwork — rare/common render
 * nothing here (their treatment is a ring, applied by the caller). */
export function RarityCorners({ rarity }: { rarity: Rarity }) {
  if (!RARITY_HAS_CORNERS[rarity]) return null;
  const color = BORDER_COLOR[rarity];
  const corners =
    rarity === "legendary"
      ? (["top-0 left-0 border-t border-l", "top-0 right-0 border-t border-r", "bottom-0 left-0 border-b border-l", "bottom-0 right-0 border-b border-r"] as const)
      : (["top-0 left-0 border-t border-l", "bottom-0 right-0 border-b border-r"] as const);

  return (
    <>
      {corners.map((pos) => (
        <span key={pos} className={`pointer-events-none absolute h-3 w-3 ${pos} ${color}`} />
      ))}
    </>
  );
}
