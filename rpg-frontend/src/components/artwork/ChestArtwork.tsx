import { ArtFrame, type ArtworkSize } from "./ArtFrame";
import type { ChestOut } from "@/types";
import { staticUrl } from "@/utils/staticUrl";

interface ChestArtworkProps {
  chest: Pick<ChestOut, "name" | "image_path" | "guaranteed_min_rarity">;
  size?: ArtworkSize;
  className?: string;
}

/** A chest isn't itself one rarity (it rolls from `rarity_probabilities`),
 * so unlike ItemArtwork this only uses `guaranteed_min_rarity` as a floor
 * hint on the frame, not a full rarity treatment. */
export function ChestArtwork({ chest, size = "card", className }: ChestArtworkProps) {
  return (
    <ArtFrame
      src={staticUrl(chest.image_path)}
      alt={chest.name}
      size={size}
      variant="ember"
      rarity={chest.guaranteed_min_rarity ?? undefined}
      className={className}
    />
  );
}
