import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { ErrorState, Skeleton } from "@/components/ui";
import { useClaimQuest, useQuests } from "@/hooks/useQuests";
import type { QuestOut } from "@/types";
import { formatNumber } from "@/utils/format";

const CONDITION_ICON: Record<string, string> = {
  battles_won: "⚔",
  expeditions_claimed: "🧭",
  chests_opened: "🗝",
  hero_level: "★",
  items_equipped: "🛡",
  skills_upgraded: "✦",
  arena_wins: "🏆",
  campaign_nodes_cleared: "🗺",
};

function QuestRow({ quest }: { quest: QuestOut }) {
  const claim = useClaimQuest();
  const pct = Math.min(100, Math.round((quest.current_progress / quest.target_value) * 100));

  return (
    <div className="flex items-center gap-3 rounded-lg border border-hairline bg-bg-surface p-2.5">
      <div className="flex h-9 w-9 flex-none items-center justify-center rounded-md border border-hairline bg-bg-raised text-base">
        {CONDITION_ICON[quest.condition_type] ?? "•"}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[12.5px] font-bold text-ink">{quest.name}</p>
        {quest.description && <p className="truncate text-[10.5px] text-ink-dim">{quest.description}</p>}
        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-bg-raised">
          <div
            className={`h-full rounded-full ${quest.is_claimed ? "bg-iron-teal" : "bg-ember"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="mt-1 font-mono text-[9px] text-ink-dim">
          {Math.min(quest.current_progress, quest.target_value)}/{quest.target_value}
        </p>
      </div>
      {quest.is_claimed ? (
        <span className="flex-none font-mono text-[10px] text-ink-dim">✓ получено</span>
      ) : quest.is_completed ? (
        <button
          onClick={() => claim.mutate(quest.id)}
          disabled={claim.isPending}
          className="flex-none rounded-md bg-gradient-to-b from-ember-bright to-ember px-3 py-1.5 font-mono text-[10.5px] font-bold text-[#1D1204] disabled:opacity-50"
        >
          {claim.isPending ? "..." : "Забрать"}
        </button>
      ) : (
        <span className="flex-none whitespace-nowrap font-mono text-[10px] text-rarity-legendary">
          +{formatNumber(quest.reward_coins)}⏣
        </span>
      )}
    </div>
  );
}

export function QuestsPage() {
  const quests = useQuests();
  const active = quests.data?.filter((q) => q.is_active_slot) ?? [];
  const history = quests.data?.filter((q) => !q.is_active_slot) ?? [];

  return (
    <div className="pb-6">
      <ScreenHeader title="Квесты" />
      <div className="px-4">
        {quests.isPending && (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        )}
        {quests.isError && <ErrorState error={quests.error} onRetry={() => quests.refetch()} />}
      </div>

      {active.length > 0 && (
        <div className="px-4">
          <p className="mb-2 font-mono text-[10px] uppercase tracking-wide text-ink-dim">Активные</p>
          <div className="flex flex-col gap-2">
            {active.map((q) => (
              <QuestRow key={q.id} quest={q} />
            ))}
          </div>
        </div>
      )}

      {history.length > 0 && (
        <div className="mt-5 px-4">
          <p className="mb-2 font-mono text-[10px] uppercase tracking-wide text-ink-dim">История</p>
          <div className="flex flex-col gap-2">
            {history.map((q) => (
              <QuestRow key={q.id} quest={q} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
