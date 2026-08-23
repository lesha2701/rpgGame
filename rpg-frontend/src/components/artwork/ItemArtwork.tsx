import { ArtFrame, type ArtworkSize } from "./ArtFrame";
import type { ItemTemplateOut } from "@/types";
import { staticUrl } from "@/utils/staticUrl";

interface ItemArtworkProps {
  item: Pick<ItemTemplateOut, "name" | "image_path" | "rarity">;
  size?: ArtworkSize;
  className?: string;
}

/** The one artwork wrapper with a real, backend-provided rarity — items are
 * the only entity in this API that carries `rarity` on the template itself. */
export function ItemArtwork({ item, size = "card", className }: ItemArtworkProps) {
  return (
    <ArtFrame
      src={staticUrl(item.image_path)}
      alt={item.name}
      size={size}
      variant="epic-wash"
      rarity={item.rarity}
      className={className}
    />
  );
}
