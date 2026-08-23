import { Link } from "react-router-dom";

import { ChestArtwork } from "@/components/artwork";
import type { ChestOut } from "@/types";
import { formatNumber } from "@/utils/format";

// slug === "free-chest" is the real identifier (see rpg-backend's
// free_chest_service.py) — price === 0 alone isn't reliable enough to route
// the open call correctly (the generic POST /chests/{id}/open has no
// cooldown concept at all; only POST /chests/free/claim enforces it).
const isFree = (chest: Pick<ChestOut, "slug">) => chest.slug === "free-chest";

export function ChestCard({ chest }: { chest: ChestOut }) {
  const free = isFree(chest);
  return (
    <Link
      to={`/chests/${chest.id}/open`}
      className={`block overflow-hidden rounded-lg border bg-bg-surface ${
        free ? "border-rarity-legendary shadow-glow-legendary animate-legendary-breathe" : "border-hairline"
      }`}
    >
      <ChestArtwork chest={chest} size="card" className="rounded-none" />
      <div className="p-2.5">
        <p className="font-display text-[14px] font-semibold text-ink">{chest.name}</p>
        <span className={`font-mono text-[11px] font-bold ${free ? "text-rarity-legendary" : "text-ink-mute"}`}>
          {free ? "Бесплатно" : `${formatNumber(chest.price)} ⏣`}
        </span>
      </div>
    </Link>
  );
}
