import { ArtFrame, type ArtworkSize } from "./ArtFrame";
import type { HeroTemplateOut } from "@/types";
import { staticUrl } from "@/utils/staticUrl";

interface CharacterArtworkProps {
  template: HeroTemplateOut;
  size?: ArtworkSize;
  /** Hero portraits are the one artwork type the product explicitly wants
   * user-uploaded photos for (not AI-generated) — Home/Hero pass this so the
   * empty state reads as an upload prompt rather than a silent wash. */
  showUploadHint?: boolean;
  className?: string;
}

/** `template.image_path` is real backend data — now backed by a real file
 * once an admin has uploaded one (rpg-backend's admin_hero_templates.py +
 * static-asset serving, added alongside this). Still renders ArtFrame's
 * empty state whenever a template has no upload yet, which remains the
 * common case for most content. */
export function CharacterArtwork({ template, size = "card", showUploadHint, className }: CharacterArtworkProps) {
  return (
    <ArtFrame
      src={staticUrl(template.image_path)}
      alt={template.name}
      size={size}
      variant="ember"
      emptyHint={showUploadHint ? "Загрузите фото персонажа" : undefined}
      className={className}
    />
  );
}
