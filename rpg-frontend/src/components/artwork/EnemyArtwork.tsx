import { ArtFrame, type ArtworkSize } from "./ArtFrame";
import type { EnemyOut } from "@/types";
import { staticUrl } from "@/utils/staticUrl";

interface EnemyArtworkProps {
  enemy: Pick<EnemyOut, "name" | "image_path">;
  size?: ArtworkSize;
  className?: string;
}

export function EnemyArtwork({ enemy, size = "card", className }: EnemyArtworkProps) {
  return (
    <ArtFrame src={staticUrl(enemy.image_path)} alt={enemy.name} size={size} variant="frost" className={className} />
  );
}
