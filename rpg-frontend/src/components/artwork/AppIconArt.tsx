import { ArtFrame, type ArtworkSize, type ArtworkVariant } from "./ArtFrame";
import { staticUrl } from "@/utils/staticUrl";

interface AppIconArtProps {
  imagePath: string | null | undefined;
  alt: string;
  size?: ArtworkSize;
  variant?: ArtworkVariant;
  className?: string;
}

/** Renders one admin-uploadable UI icon (bottom nav / Battle hub rows /
 * More page rows) through the same ArtFrame empty-state machinery every
 * game-content image already uses — no emoji, no procedural fallback: an
 * unset slot is just ArtFrame's plain colored wash until an admin
 * uploads something (see AppIcon's backend docstring). */
export function AppIconArt({ imagePath, alt, size = "thumbnail", variant = "ember", className }: AppIconArtProps) {
  return <ArtFrame src={staticUrl(imagePath)} alt={alt} size={size} variant={variant} className={className} />;
}
