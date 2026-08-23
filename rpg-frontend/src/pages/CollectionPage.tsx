import { Link } from "react-router-dom";

import { CharacterArtwork } from "@/components/artwork";
import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { ErrorState, Skeleton } from "@/components/ui";
import { useHeroTemplates } from "@/hooks/useCatalog";
import { useSession } from "@/hooks/useSession";

/** Reinterpretation, not a real backend feature: there is no multi-hero
 * ownership concept (User.active_hero_id is singular — see
 * FRONTEND_API_MAP.md). "Collection" here is the game's hero-template
 * catalog (GET /hero-templates, real) with "unlocked" derived from whether
 * that template matches the user's own active hero (also real). This is
 * NOT a roster of owned heroes — flagged for confirmation, not silently
 * decided as final. */
export function CollectionPage() {
  const templates = useHeroTemplates();
  const session = useSession();

  const ownedTemplateId = session.data?.user.active_hero?.hero_template.id;

  return (
    <div>
      <ScreenHeader title="Коллекция" />
      <p className="px-4 pb-4 text-[12px] leading-relaxed text-ink-dim">
        Каталог героев игры. У бэкенда нет мульти-геройного владения — «разблокирован» здесь означает «это герой,
        которого вы выбрали», а не отдельно хранимый прогресс коллекции.
      </p>
      <div className="grid grid-cols-2 gap-3 px-4 pb-6">
        {templates.isPending &&
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="aspect-[3/4]" />)}
        {templates.isError && (
          <div className="col-span-2">
            <ErrorState error={templates.error} onRetry={() => templates.refetch()} />
          </div>
        )}
        {templates.data?.map((t) => {
          const owned = t.id === ownedTemplateId;
          return (
            <Link key={t.id} to={`/collection/${t.id}`} className="block overflow-hidden rounded-lg border border-hairline bg-bg-surface">
              <div className="relative">
                <CharacterArtwork template={t} size="card" className={`rounded-none ${owned ? "" : "grayscale"}`} />
                {!owned && (
                  <span className="absolute inset-0 flex items-center justify-center text-lg opacity-70" aria-hidden>
                    🔒
                  </span>
                )}
              </div>
              <div className="p-2.5">
                <p className="text-[12.5px] font-bold text-ink">{t.name}</p>
                <p className="font-mono text-[10px] text-ink-dim">
                  {owned ? "выбран" : `${t.race.name} · ${t.character_class.name}`}
                </p>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
