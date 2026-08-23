import { CharacterArtwork } from "@/components/artwork";
import { ErrorState, LinkButton, Pill, Skeleton, StageTrack, StatChip, XpBar } from "@/components/ui";
import { useMyProfile } from "@/hooks/useProfile";
import { useSession } from "@/hooks/useSession";
import { formatNumber, heroTagline } from "@/utils/format";

function HeroSkeleton() {
  return (
    <div className="relative h-[calc(100vh-64px)] min-h-[560px]">
      <Skeleton className="absolute inset-0 rounded-none" />
    </div>
  );
}

/** The app's home/landing screen and the hero detail screen were the exact
 * same content twice (Home and Hero used to be separate routes) — merged
 * into one, which is now what "/" renders. Bottom nav's old "Дом" slot
 * became Chests instead (see BottomNav.tsx); this screen keeps living at
 * "/" and "Герой" links here directly now. */
export function HeroPage() {
  const session = useSession();
  const profile = useMyProfile();

  if (session.isPending) return <HeroSkeleton />;
  if (session.isError) {
    return (
      <div className="p-4">
        <ErrorState error={session.error} onRetry={() => session.refetch()} />
      </div>
    );
  }

  const hero = session.data.user.active_hero;

  // SessionGate renders CharacterCreationScreen instead of any route
  // (including this one) whenever active_hero is null, so this is
  // unreachable in practice — kept only so TypeScript's null check is
  // satisfied without an assertion.
  if (!hero) return null;

  const template = hero.hero_template;

  return (
    <div className="relative h-[calc(100vh-64px)] min-h-[560px] overflow-hidden">
      <CharacterArtwork template={template} size="full-bleed" showUploadHint />
      <div className="absolute inset-x-0 bottom-0 h-[62%] bg-gradient-to-t from-bg-base via-bg-base/90 to-transparent" />

      <div className="absolute inset-x-0 top-0 flex items-center justify-between p-4">
        {profile.data ? (
          <Pill>
            <span className="h-1.5 w-1.5 rounded-full bg-rarity-legendary" />
            {formatNumber(profile.data.balance)}
          </Pill>
        ) : (
          <Skeleton className="h-[30px] w-[86px] rounded-full" />
        )}
      </div>

      <div className="absolute inset-x-0 bottom-0 flex flex-col gap-3 p-4">
        <div className="flex items-baseline gap-2">
          <span className="font-display text-2xl font-semibold text-ink">{hero.name}</span>
          <span className="font-mono text-[10.5px] uppercase tracking-wide text-ink-mute">
            {heroTagline(template.race.name, template.character_class.name)}
          </span>
        </div>

        <StageTrack visualStage={hero.visual_stage} />
        <XpBar
          xp={hero.xp}
          xpToNextLevel={hero.xp_to_next_level}
          label={`Уровень ${hero.level} · Стадия ${hero.visual_stage}`}
        />

        <div className="flex gap-1.5">
          <StatChip value={hero.stats.hp} label="HP" />
          <StatChip value={hero.stats.attack} label="ATK" />
          <StatChip value={hero.stats.defense} label="DEF" />
          <StatChip value={hero.stats.speed} label="SPD" />
        </div>

        <div className="flex gap-1.5 pt-1">
          <LinkButton to="/hero/progression" variant="secondary" className="flex-1">
            Путь развития
          </LinkButton>
          <LinkButton to="/inventory" className="flex-1">
            Инвентарь
          </LinkButton>
        </div>
      </div>
    </div>
  );
}
