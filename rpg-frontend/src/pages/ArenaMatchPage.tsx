import { useParams } from "react-router-dom";

import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { Button, ErrorState, Skeleton } from "@/components/ui";
import { useMatch, useSubmitAction } from "@/hooks/useArena";
import { useMySkills } from "@/hooks/useSkills";
import { useSession } from "@/hooks/useSession";
import type { ArenaParticipantOut } from "@/types";

function ParticipantPanel({ participant, label }: { participant: ArenaParticipantOut; label: string }) {
  const pct = Math.max(0, (participant.current_hp / participant.max_hp) * 100);
  return (
    <div className="flex-1">
      <p className="font-mono text-[9.5px] uppercase tracking-wide text-ink-dim">{label}</p>
      <p className="truncate text-[13px] font-bold text-ink">{participant.hero_name}</p>
      <div className="mt-1.5 flex justify-between font-mono text-[10px] text-ink-mute">
        <span>HP</span>
        <span>
          {participant.current_hp}/{participant.max_hp}
        </span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-bg-raised">
        <div
          className="h-full rounded-full bg-gradient-to-r from-rarity-epic to-[#C48FE8]"
          style={{ width: `${pct}%` }}
        />
      </div>
      {participant.has_acted_this_round && (
        <p className="mt-1 font-mono text-[9.5px] text-iron-teal-bright">действие выбрано</p>
      )}
    </div>
  );
}

export function ArenaMatchPage() {
  const { matchId } = useParams<{ matchId: string }>();
  const id = Number(matchId);
  const match = useMatch(id);
  const session = useSession();
  const skills = useMySkills();
  const submitAction = useSubmitAction(id);

  if (match.isPending) {
    return (
      <div>
        <ScreenHeader title="Матч" />
        <div className="flex flex-col gap-2 px-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      </div>
    );
  }

  if (match.isError) {
    return (
      <div>
        <ScreenHeader title="Матч" />
        <div className="p-4">
          <ErrorState error={match.error} onRetry={() => match.refetch()} />
        </div>
      </div>
    );
  }

  const m = match.data;
  const myUserId = session.data?.user.id;
  const mine = m.player_a.user_id === myUserId ? m.player_a : m.player_b;
  const opponent = m.player_a.user_id === myUserId ? m.player_b : m.player_a;
  const canAct = m.status === "running" && !mine.has_acted_this_round;

  return (
    <div className="pb-6">
      <ScreenHeader title={`vs ${opponent.hero_name}`} />

      <div className="px-4">
        <div className="flex items-center gap-3">
          <ParticipantPanel participant={mine} label="Вы" />
          <span className="font-display text-sm font-semibold text-ink-dim">VS</span>
          <ParticipantPanel participant={opponent} label="Соперник" />
        </div>

        <p className="mt-3 text-center font-mono text-[10.5px] text-ink-dim">
          {m.status === "running" ? `Раунд ${m.current_round}` : "Матч завершён"}
        </p>

        {m.status === "finished" && (
          <div className="mt-3 rounded-md border border-hairline bg-bg-surface p-3 text-center">
            <p
              className={`font-mono text-[11px] font-bold uppercase ${
                m.winner_user_id === myUserId ? "text-iron-teal-bright" : "text-crimson-bright"
              }`}
            >
              {m.winner_user_id === myUserId ? "Победа" : m.winner_user_id ? "Поражение" : "Ничья"}
            </p>
            {m.winner_user_id === myUserId && (
              <p className="mt-1 font-mono text-[10px] text-ink-dim">
                +{m.reward_xp} XP · +{m.reward_coins} ⏣
              </p>
            )}
          </div>
        )}

        {submitAction.isError && (
          <div className="mt-3">
            <ErrorState error={submitAction.error} />
          </div>
        )}

        {canAct && (
          <div className="mt-4 flex flex-col gap-1.5">
            <Button
              variant="secondary"
              disabled={submitAction.isPending}
              onClick={() => submitAction.mutate({ round: m.current_round, action_type: "basic_attack" })}
            >
              Обычная атака
            </Button>
            {skills.data?.map((s) => (
              <Button
                key={s.id}
                variant="secondary"
                disabled={submitAction.isPending}
                onClick={() =>
                  submitAction.mutate({
                    round: m.current_round,
                    action_type: "skill",
                    skill_id: s.skill_definition.id,
                  })
                }
              >
                {s.skill_definition.name}
              </Button>
            ))}
          </div>
        )}

        {m.status === "running" && !canAct && (
          <p className="mt-4 text-center font-mono text-[10.5px] text-ink-dim">
            Действие отправлено — ждём соперника (обновляется автоматически)
          </p>
        )}

        <div className="mt-5">
          <p className="mb-1.5 font-mono text-[9.5px] uppercase tracking-wide text-ink-dim">Лог боя</p>
          <div className="flex flex-col gap-1">
            {m.log
              .slice()
              .reverse()
              .slice(0, 8)
              .map((entry, i) => (
                <div key={i} className="rounded border border-hairline bg-bg-surface px-2.5 py-1.5 text-[11px] text-ink-mute">
                  {entry.attacker === "player_a" ? m.player_a.hero_name : m.player_b.hero_name}{" "}
                  {entry.action_type === "skill" ? "применил способность" : "атаковал"} →{" "}
                  {entry.target === "player_a" ? m.player_a.hero_name : m.player_b.hero_name} (−{entry.damage}
                  {entry.critical ? ", крит" : ""})
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}
