import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { ErrorState, Skeleton } from "@/components/ui";
import { useSession } from "@/hooks/useSession";
import { stagePath } from "@/utils/progression";

/** Real data: hero.visual_stage (server-computed) and hero.level. Mocked:
 * per-stage artwork thumbnails — Stage 12's artwork pipeline doesn't exist
 * yet, see FRONTEND_API_MAP.md. The unlock-level labels are derived from
 * the same LEVELS_PER_TIER cadence the backend itself uses, not invented. */
export function HeroProgressionPage() {
  const session = useSession();

  if (session.isPending) {
    return (
      <div>
        <ScreenHeader title="Путь развития" />
        <div className="flex flex-col gap-2 px-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      </div>
    );
  }
  if (session.isError) {
    return (
      <div>
        <ScreenHeader title="Путь развития" />
        <div className="p-4">
          <ErrorState error={session.error} onRetry={() => session.refetch()} />
        </div>
      </div>
    );
  }

  const hero = session.data.user.active_hero;
  const currentStage = hero?.visual_stage ?? 1;
  const stages = [...stagePath()].reverse();

  return (
    <div>
      <ScreenHeader title="Путь развития" />
      <p className="px-4 pb-4 text-[12.5px] leading-relaxed text-ink-mute">
        Стадии героя — <code className="font-mono text-ink">visual_stage</code>, вычисляется сервером из уровня.
        Изображения по стадиям появятся с Stage 12 backend (artwork pipeline) — пока показан только номер тира.
      </p>
      <div className="relative flex flex-col-reverse px-4 pb-8">
        <div className="absolute bottom-8 left-[27px] top-4 w-px bg-gradient-to-b from-hairline via-ember to-rarity-legendary" />
        {stages.map(({ stage, unlockLevel }) => {
          const isDone = stage < currentStage;
          const isCurrent = stage === currentStage;
          const isLocked = stage > currentStage;

          return (
            <div key={stage} className="relative flex items-center gap-3 py-2 pl-9">
              <div
                className={`absolute left-0 flex h-5 w-5 items-center justify-center rounded-full border-2 bg-bg-base font-mono text-[9px] font-bold ${
                  isCurrent
                    ? "border-rarity-legendary text-rarity-legendary shadow-glow-legendary"
                    : isDone
                      ? "border-ember-deep text-ember-bright"
                      : "border-hairline text-ink-dim"
                }`}
              >
                {stage}
              </div>
              <div
                className={`h-14 w-11 flex-none rounded-md border ${
                  isCurrent ? "border-rarity-legendary shadow-glow-legendary" : "border-hairline"
                } bg-gradient-to-br from-bg-raised to-bg-surface flex items-center justify-center`}
                style={{ opacity: isLocked ? 1 : isCurrent ? 1 : 0.3 + (0.5 * stage) / currentStage }}
              >
                {isLocked && (
                  <span className="text-xs opacity-50" aria-hidden>
                    🔒
                  </span>
                )}
              </div>
              <div>
                <p className={`font-display text-sm font-semibold ${isLocked ? "text-ink-dim" : "text-ink"}`}>
                  Стадия {stage}
                  {isCurrent && " · Текущая"}
                </p>
                <p className="font-mono text-[10px] text-ink-dim">
                  {isLocked ? `с уровня ${unlockLevel}` : isCurrent ? "" : "пройдена"}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
