import { useState } from "react";
import { Link } from "react-router-dom";

import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { Button, ErrorState, Skeleton } from "@/components/ui";
import { useCreateMatch, useMatches } from "@/hooks/useArena";
import { useSession } from "@/hooks/useSession";
import type { ArenaMatchOut } from "@/types";

function opponentOf(match: ArenaMatchOut, myUserId: number | undefined) {
  return match.player_a.user_id === myUserId ? match.player_b : match.player_a;
}

function MatchRow({ match, myUserId }: { match: ArenaMatchOut; myUserId: number | undefined }) {
  const opponent = opponentOf(match, myUserId);
  const won = match.status === "finished" && match.winner_user_id === myUserId;
  const lost = match.status === "finished" && match.winner_user_id !== null && match.winner_user_id !== myUserId;

  return (
    <Link
      to={`/arena/matches/${match.id}`}
      className="flex items-center gap-3 rounded-lg border border-hairline bg-bg-surface px-3 py-2.5"
    >
      <div className="flex-1">
        <p className="text-[13px] font-bold text-ink">vs {opponent.hero_name}</p>
        <p className="font-mono text-[10px] text-ink-dim">
          {match.status === "running" ? `раунд ${match.current_round}` : "завершён"}
        </p>
      </div>
      {match.status === "running" && (
        <span className="rounded bg-rarity-epic/15 px-2 py-1 font-mono text-[9.5px] font-bold text-rarity-epic">
          идёт
        </span>
      )}
      {won && (
        <span className="rounded bg-iron-teal/15 px-2 py-1 font-mono text-[9.5px] font-bold text-iron-teal-bright">
          победа
        </span>
      )}
      {lost && (
        <span className="rounded bg-crimson/15 px-2 py-1 font-mono text-[9.5px] font-bold text-crimson-bright">
          поражение
        </span>
      )}
    </Link>
  );
}

export function ArenaPage() {
  const matches = useMatches();
  const session = useSession();
  const createMatch = useCreateMatch();
  const [opponentId, setOpponentId] = useState("");

  const myUserId = session.data?.user.id;

  return (
    <div className="pb-6">
      <ScreenHeader title="Арена" />

      <div className="px-4">
        <div className="rounded-lg border border-dashed border-hairline bg-bg-surface p-3">
          <p className="mb-2 font-mono text-[10px] leading-relaxed text-ink-dim">
            У backend пока нет поиска соперников (см. FRONTEND_API_MAP.md) — вручную укажите ID пользователя, чтобы
            создать матч.
          </p>
          <div className="flex gap-2">
            <input
              value={opponentId}
              onChange={(e) => setOpponentId(e.target.value)}
              placeholder="ID соперника"
              inputMode="numeric"
              className="flex-1 rounded-md border border-hairline bg-bg-raised px-3 py-2 font-mono text-[12px] text-ink outline-none"
            />
            <Button
              variant="secondary"
              disabled={!opponentId || createMatch.isPending}
              onClick={() => createMatch.mutate({ opponent_user_id: Number(opponentId) })}
            >
              {createMatch.isPending ? "..." : "Вызвать"}
            </Button>
          </div>
          {createMatch.isError && <div className="mt-2"><ErrorState error={createMatch.error} /></div>}
          {createMatch.isSuccess && (
            <Link to={`/arena/matches/${createMatch.data.id}`} className="mt-2 block text-center font-mono text-[11px] text-ember-bright">
              Матч создан → открыть
            </Link>
          )}
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-2 px-4">
        {matches.isPending &&
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-14" />)}
        {matches.isError && <ErrorState error={matches.error} onRetry={() => matches.refetch()} />}
        {matches.data?.length === 0 && (
          <p className="py-6 text-center text-[13px] text-ink-dim">Матчей ещё не было.</p>
        )}
        {matches.data?.map((m) => <MatchRow key={m.id} match={m} myUserId={myUserId} />)}
      </div>
    </div>
  );
}
