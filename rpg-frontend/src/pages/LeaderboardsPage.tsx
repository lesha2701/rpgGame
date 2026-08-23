import { useState } from "react";

import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { ErrorState, Skeleton } from "@/components/ui";
import { useLeaderboard } from "@/hooks/useLeaderboards";
import { useSession } from "@/hooks/useSession";
import type { LeaderboardEntryOut, LeaderboardType } from "@/types";
import { formatNumber } from "@/utils/format";

const TABS: { type: LeaderboardType; label: string }[] = [
  { type: "level", label: "Уровень" },
  { type: "pve_wins", label: "PvE" },
  { type: "arena_wins", label: "Арена" },
  { type: "coins", label: "Монеты" },
];

function displayName(entry: LeaderboardEntryOut): string {
  return entry.username ?? entry.hero?.name ?? `Игрок #${entry.user_id}`;
}

function initial(entry: LeaderboardEntryOut): string {
  return displayName(entry).charAt(0).toUpperCase();
}

function PodiumSlot({ entry, place }: { entry: LeaderboardEntryOut; place: 1 | 2 | 3 }) {
  const ring = place === 1 ? "border-rarity-legendary shadow-glow-legendary" : place === 2 ? "border-rarity-common" : "border-[#A9713D]";
  const size = place === 1 ? "h-[58px] w-[58px] text-xl" : "h-11 w-11 text-base";
  return (
    <div className="flex w-20 flex-col items-center">
      <div
        className={`flex items-center justify-center rounded-full border-2 bg-gradient-to-br from-bg-raised to-bg-surface font-display font-semibold text-ink-mute ${ring} ${size}`}
      >
        {initial(entry)}
      </div>
      <p className="mt-1.5 truncate text-[11px] font-bold text-ink">{displayName(entry)}</p>
      <p className="font-mono text-[9.5px] text-ink-dim">{formatNumber(entry.value)}</p>
    </div>
  );
}

export function LeaderboardsPage() {
  const [type, setType] = useState<LeaderboardType>("level");
  const leaderboard = useLeaderboard(type, 20, 0);
  const session = useSession();
  const myUserId = session.data?.user.id;

  return (
    <div className="pb-6">
      <ScreenHeader title="Лидерборды" />

      <div className="mb-4 flex gap-1 px-4">
        {TABS.map((t) => (
          <button
            key={t.type}
            onClick={() => setType(t.type)}
            className={`flex-1 rounded-md py-1.5 font-mono text-[9.5px] font-bold uppercase ${
              type === t.type ? "bg-ember text-[#1D1204]" : "bg-bg-raised text-ink-dim"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="px-4">
        {leaderboard.isPending && (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-11" />
            ))}
          </div>
        )}

        {leaderboard.isError && <ErrorState error={leaderboard.error} onRetry={() => leaderboard.refetch()} />}

        {leaderboard.data && leaderboard.data.entries.length === 0 && (
          <p className="py-10 text-center text-[13px] text-ink-dim">Пока никто не попал в этот рейтинг.</p>
        )}

        {leaderboard.data && leaderboard.data.entries.length > 0 && (
          <>
            <div className="mb-5 flex items-end justify-center gap-3 pt-3">
              {leaderboard.data.entries[1] && <PodiumSlot entry={leaderboard.data.entries[1]} place={2} />}
              {leaderboard.data.entries[0] && <PodiumSlot entry={leaderboard.data.entries[0]} place={1} />}
              {leaderboard.data.entries[2] && <PodiumSlot entry={leaderboard.data.entries[2]} place={3} />}
            </div>

            <div className="flex flex-col">
              {leaderboard.data.entries.slice(3).map((entry) => (
                <div
                  key={entry.user_id}
                  className={`flex items-center gap-3 border-t border-hairline py-2 ${
                    entry.user_id === myUserId ? "-mx-4 border-ember bg-ember/10 px-4" : ""
                  }`}
                >
                  <span className="w-6 font-mono text-[11px] font-bold text-ink-dim">{entry.rank}</span>
                  <span className="flex-1 text-[12.5px] font-semibold text-ink">{displayName(entry)}</span>
                  <span className="font-mono text-[12px] font-bold text-ember-bright">{formatNumber(entry.value)}</span>
                </div>
              ))}
            </div>

            {leaderboard.data.my_rank && leaderboard.data.my_rank > leaderboard.data.entries.length && (
              <div className="mt-3 flex items-center gap-3 rounded-md border border-ember bg-ember/10 px-3 py-2">
                <span className="w-6 font-mono text-[11px] font-bold text-ember-bright">{leaderboard.data.my_rank}</span>
                <span className="flex-1 text-[12.5px] font-semibold text-ink">Вы</span>
                <span className="font-mono text-[12px] font-bold text-ember-bright">
                  {formatNumber(leaderboard.data.my_value)}
                </span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
