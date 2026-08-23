import { Link } from "react-router-dom";

import { EnemyArtwork } from "@/components/artwork";
import type { EnemyOut } from "@/types";

export function EnemyCard({ enemy }: { enemy: EnemyOut }) {
  const locked = !enemy.is_available_to_user;
  return (
    <Link
      to={`/bestiary/${enemy.id}`}
      className={`block overflow-hidden rounded-lg border border-hairline bg-bg-surface ${locked ? "opacity-60" : ""}`}
    >
      <div className="relative">
        <EnemyArtwork enemy={enemy} size="card" className={`rounded-none ${locked ? "grayscale" : ""}`} />
        {locked && (
          <span className="absolute inset-0 flex items-center justify-center text-lg opacity-70" aria-hidden>
            🔒
          </span>
        )}
      </div>
      <div className="p-2.5">
        <p className="text-[12.5px] font-bold text-ink">{enemy.name}</p>
        <p className="font-mono text-[10px] text-ink-dim">req. lvl {enemy.level}</p>
      </div>
    </Link>
  );
}
