import { CharacterArtwork } from "@/components/artwork";
import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { ErrorState, Skeleton } from "@/components/ui";
import { useMyProfile } from "@/hooks/useProfile";
import { formatNumber } from "@/utils/format";

function StatBlock({ value, label }: { value: number; label: string }) {
  return (
    <div className="rounded-md border border-hairline bg-bg-raised px-3 py-2.5">
      <span className="block font-mono text-[15px] font-bold text-ink">{formatNumber(value)}</span>
      <span className="block font-mono text-[9.5px] uppercase tracking-wide text-ink-dim">{label}</span>
    </div>
  );
}

export function ProfilePage() {
  const profile = useMyProfile();

  if (profile.isPending) {
    return (
      <div>
        <ScreenHeader title="Статистика" />
        <div className="flex flex-col gap-3 px-4">
          <Skeleton className="h-16" />
          <div className="grid grid-cols-2 gap-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (profile.isError) {
    return (
      <div>
        <ScreenHeader title="Статистика" />
        <div className="p-4">
          <ErrorState error={profile.error} onRetry={() => profile.refetch()} />
        </div>
      </div>
    );
  }

  const { user, balance, statistics } = profile.data;
  const hero = user.active_hero;

  return (
    <div className="pb-6">
      <ScreenHeader title="Статистика" />

      <div className="flex items-center gap-3 px-4 pb-5">
        {hero ? (
          <CharacterArtwork template={hero.hero_template} size="thumbnail" className="w-14" />
        ) : (
          <div className="h-14 w-14 rounded-md bg-bg-raised" />
        )}
        <div>
          <p className="font-display text-lg font-semibold text-ink">
            {user.first_name ?? user.username ?? `Игрок #${user.id}`}
          </p>
          <p className="font-mono text-[11px] text-ink-dim">
            {hero ? `lvl ${hero.level} · стадия ${hero.visual_stage}` : "без героя"}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 px-4">
        <StatBlock value={balance} label="Монеты" />
        <StatBlock value={statistics.battles.wins} label="PvE побед" />
        <StatBlock value={statistics.battles.played - statistics.battles.wins} label="PvE поражений" />
        <StatBlock value={statistics.arena.wins} label="Arena побед" />
        <StatBlock value={statistics.arena.played - statistics.arena.wins} label="Arena поражений" />
        <StatBlock value={statistics.campaign.nodes_cleared} label="Узлов кампании" />
        <StatBlock value={statistics.campaign.total_clears} label="Побед в кампании" />
        <StatBlock value={statistics.expeditions.claimed} label="Экспедиций" />
        <StatBlock value={statistics.quests.claimed} label="Квестов" />
        <StatBlock value={statistics.chests.opened} label="Сундуков" />
        <StatBlock value={statistics.hero_activity.items_equipped} label="Экипировано" />
        <StatBlock value={statistics.hero_activity.skills_upgraded} label="Улучшений навыков" />
        <StatBlock value={statistics.referrals.referral_count} label="Рефералов" />
        <StatBlock value={statistics.referrals.successful_referrals} label="Успешных" />
      </div>
    </div>
  );
}
