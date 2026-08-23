import { useParams } from "react-router-dom";

import { CharacterArtwork } from "@/components/artwork";
import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { ErrorState, Skeleton, StatChip, XpBar } from "@/components/ui";
import { useHeroTemplates } from "@/hooks/useCatalog";
import { useSession } from "@/hooks/useSession";
import { heroTagline } from "@/utils/format";

export function CharacterDetailPage() {
  const { templateId } = useParams<{ templateId: string }>();
  const templates = useHeroTemplates();
  const session = useSession();

  if (templates.isPending || session.isPending) {
    return (
      <div>
        <ScreenHeader title="Персонаж" />
        <div className="px-4">
          <Skeleton className="aspect-[3/4]" />
        </div>
      </div>
    );
  }

  if (templates.isError) {
    return (
      <div>
        <ScreenHeader title="Персонаж" />
        <div className="p-4">
          <ErrorState error={templates.error} onRetry={() => templates.refetch()} />
        </div>
      </div>
    );
  }

  const template = templates.data.find((t) => t.id === Number(templateId));
  if (!template) {
    return (
      <div>
        <ScreenHeader title="Персонаж" />
        <div className="p-4">
          <ErrorState error={new Error("template not found")} />
        </div>
      </div>
    );
  }

  const hero = session.data?.user.active_hero;
  const owned = hero?.hero_template.id === template.id;
  const cls = template.character_class;

  return (
    <div className="pb-6">
      <ScreenHeader title={template.name} />
      <div className="px-4">
        <CharacterArtwork template={template} size="detail" className={`w-full ${owned ? "" : "grayscale"}`} />

        <div className="mt-3">
          <p className="font-display text-xl font-semibold text-ink">{template.name}</p>
          <p className="font-mono text-[11px] uppercase tracking-wide text-ink-mute">
            {heroTagline(template.race.name, cls.name)}
          </p>
        </div>

        {template.description && <p className="mt-2 text-[13px] leading-relaxed text-ink-mute">{template.description}</p>}

        {owned && hero ? (
          <>
            <div className="mt-4 flex gap-1.5">
              <StatChip value={hero.stats.hp} label="HP" />
              <StatChip value={hero.stats.attack} label="ATK" />
              <StatChip value={hero.stats.defense} label="DEF" />
              <StatChip value={hero.stats.speed} label="SPD" />
            </div>
            <div className="mt-3">
              <XpBar xp={hero.xp} xpToNextLevel={hero.xp_to_next_level} label={`Уровень ${hero.level}`} />
            </div>
          </>
        ) : (
          <>
            <p className="mt-4 font-mono text-[10.5px] uppercase tracking-wide text-ink-dim">
              🔒 Не выбран · базовые характеристики (1 уровень)
            </p>
            <div className="mt-2 flex gap-1.5">
              <StatChip value={cls.base_hp} label="HP" />
              <StatChip value={cls.base_attack} label="ATK" />
              <StatChip value={cls.base_defense} label="DEF" />
              <StatChip value={cls.base_speed} label="SPD" />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
