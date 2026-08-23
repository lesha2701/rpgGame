import { useParams } from "react-router-dom";

import { EnemyArtwork } from "@/components/artwork";
import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { ErrorState, Skeleton, StatChip } from "@/components/ui";
import { useEnemy } from "@/hooks/useEnemies";
import { formatNumber } from "@/utils/format";

export function EnemyDetailPage() {
  const { enemyId } = useParams<{ enemyId: string }>();
  const enemy = useEnemy(Number(enemyId));

  if (enemy.isPending) {
    return (
      <div>
        <ScreenHeader title="Враг" />
        <div className="px-4">
          <Skeleton className="aspect-[3/4]" />
        </div>
      </div>
    );
  }

  if (enemy.isError) {
    return (
      <div>
        <ScreenHeader title="Враг" />
        <div className="p-4">
          <ErrorState error={enemy.error} onRetry={() => enemy.refetch()} />
        </div>
      </div>
    );
  }

  const e = enemy.data;

  return (
    <div className="pb-6">
      <ScreenHeader title={e.name} />
      <div className="px-4">
        <EnemyArtwork enemy={e} size="detail" className="w-full" />
        {e.description && <p className="mt-3 text-[13px] leading-relaxed text-ink-mute">{e.description}</p>}

        <div className="mt-3 flex gap-1.5">
          <StatChip value={e.hp} label="HP" />
          <StatChip value={e.attack} label="ATK" />
          <StatChip value={e.defense} label="DEF" />
          <StatChip value={e.speed} label="SPD" />
        </div>

        <div className="mt-3 flex items-center justify-between rounded-md border border-hairline bg-bg-raised px-3 py-2.5">
          <span className="font-mono text-[11px] text-ink-dim">Рекомендуемый уровень</span>
          <span className="font-mono text-[13px] font-bold text-ink">{e.level}</span>
        </div>

        <div className="mt-2 flex items-center justify-between rounded-md border border-hairline bg-bg-raised px-3 py-2.5">
          <span className="font-mono text-[11px] text-ink-dim">Награда</span>
          <span className="font-mono text-[13px] font-bold text-rarity-legendary">
            +{formatNumber(e.reward_xp)} XP · +{formatNumber(e.reward_coins)} ⏣
          </span>
        </div>

        {!e.is_available_to_user && (
          <p className="mt-3 text-center font-mono text-[10.5px] text-ink-dim">
            🔒 Недоступен — герой ещё не достиг нужного уровня
          </p>
        )}
      </div>
    </div>
  );
}
