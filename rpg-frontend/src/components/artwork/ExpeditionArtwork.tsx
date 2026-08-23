import { ArtFrame, type ArtworkSize } from "./ArtFrame";
import type { ExpeditionTemplateOut } from "@/types";
import { staticUrl } from "@/utils/staticUrl";

interface ExpeditionArtworkProps {
  expedition: Pick<ExpeditionTemplateOut, "name" | "image_path">;
  size?: ArtworkSize;
  className?: string;
}

export function ExpeditionArtwork({ expedition, size = "card", className }: ExpeditionArtworkProps) {
  return (
    <ArtFrame src={staticUrl(expedition.image_path)} alt={expedition.name} size={size} variant="frost" className={className} />
  );
}
