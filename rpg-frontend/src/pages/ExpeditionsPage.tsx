import { useEffect, useState } from "react";

import { ExpeditionArtwork } from "@/components/artwork";
import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { ErrorState, Skeleton } from "@/components/ui";
import {
  useClaimExpedition,
  useExpeditionHistory,
  useExpeditions,
  useStartExpedition,
} from "@/hooks/useExpeditions";
import type { ExpeditionTemplateOut, UserExpeditionOut } from "@/types";
import { formatNumber } from "@/utils/format";

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}ч ${m}м`;
  return `${m}м`;
}

function useNow(tickMs: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), tickMs);
    return () => clearInterval(id);
  }, [tickMs]);
  return now;
}

function ActiveExpeditionCard({ instance, template }: { instance: UserExpeditionOut; template?: ExpeditionTemplateOut }) {
  const claim = useClaimExpedition();
  const now = useNow(1000);
  const completedAt = new Date(instance.completed_at).getTime();
  const remainingMs = Math.max(0, completedAt - now);
  const ready = remainingMs <= 0;

  return (
    <div className="rounded-lg border border-iron-teal/40 bg-bg-surface p-3">
      {template ? (
        <ExpeditionArtwork expedition={template} size="battle" className="mb-2" />
      ) : (
        <div className="mb-2 h-32 rounded-md bg-[linear-gradient(100deg,rgba(79,122,110,0.35),rgba(38,33,28,0))]" />
      )}
      <p className="text-[13px] font-bold text-ink">{instance.expedition.name}</p>
      {ready ? (
        <>
          <p className="mt-1 font-mono text-[11px] text-iron-teal-bright">Экспедиция завершена</p>
          <button
            onClick={() => claim.mutate(instance.id)}
            disabled={claim.isPending}
            className="mt-2 w-full rounded-md bg-gradient-to-b from-ember-bright to-ember py-2 font-mono text-[11px] font-bold text-[#1D1204] disabled:opacity-50"
          >
            {claim.isPending ? "..." : `Забрать · +${formatNumber(instance.reward_xp)} XP · +${formatNumber(instance.reward_coins)} ⏣`}
          </button>
        </>
      ) : (
        <p className="mt-1 font-mono text-[11px] text-iron-teal-bright">
          В пути · осталось {Math.ceil(remainingMs / 1000)}с
        </p>
      )}
    </div>
  );
}

function ExpeditionTemplateCard({
  template,
  disabled,
  onStart,
  pending,
}: {
  template: ExpeditionTemplateOut;
  disabled: boolean;
  onStart: () => void;
  pending: boolean;
}) {
  const locked = !template.is_available_to_user;
  return (
    <div className={`rounded-lg border border-hairline bg-bg-surface p-3 ${locked ? "opacity-50" : ""}`}>
      <ExpeditionArtwork expedition={template} size="battle" className="mb-2" />
      <p className="text-[13px] font-bold text-ink">{template.name}</p>
      {template.description && <p className="mt-0.5 text-[10.5px] text-ink-mute">{template.description}</p>}
      <div className="mt-2 flex items-center justify-between font-mono text-[10px] text-ink-dim">
        <span>⏱ {formatDuration(template.duration_seconds)}</span>
        <span>req. lvl {template.required_hero_level}</span>
        <span className="text-rarity-legendary">
          +{formatNumber(template.reward_xp)}XP +{formatNumber(template.reward_coins)}⏣
        </span>
      </div>
      <button
        onClick={onStart}
        disabled={disabled || locked || pending}
        className="mt-2 w-full rounded-md border border-hairline bg-bg-raised py-1.5 font-mono text-[10.5px] font-bold text-ink disabled:opacity-40"
      >
        {locked ? "Недоступно" : pending ? "..." : "Отправить героя"}
      </button>
    </div>
  );
}

export function ExpeditionsPage() {
  const expeditions = useExpeditions();
  const history = useExpeditionHistory();
  const startExpedition = useStartExpedition();

  const active = history.data?.find((h) => h.status === "running" || h.status === "completed");

  return (
    <div className="pb-6">
      <ScreenHeader title="Экспедиции" />
      <div className="flex flex-col gap-3 px-4">
        {(expeditions.isPending || history.isPending) &&
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28" />)}

        {expeditions.isError && <ErrorState error={expeditions.error} onRetry={() => expeditions.refetch()} />}
        {history.isError && <ErrorState error={history.error} onRetry={() => history.refetch()} />}
        {startExpedition.isError && <ErrorState error={startExpedition.error} />}

        {active && (
          <ActiveExpeditionCard
            instance={active}
            template={expeditions.data?.find((t) => t.id === active.expedition.id)}
          />
        )}

        {expeditions.data?.map((t) => (
          <ExpeditionTemplateCard
            key={t.id}
            template={t}
            disabled={Boolean(active)}
            pending={startExpedition.isPending}
            onStart={() => startExpedition.mutate(t.id)}
          />
        ))}
      </div>
    </div>
  );
}
