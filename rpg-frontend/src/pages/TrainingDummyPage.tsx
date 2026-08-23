import { useEffect, useState } from "react";

import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { Button, ErrorState } from "@/components/ui";
import { useCompleteDummy, useStartDummy } from "@/hooks/useMinigames";
import type { MinigameResultOut } from "@/types";
import { formatNumber } from "@/utils/format";

const ROUND_MS = 1100;
const DIRECTION_ARROW: Record<string, string> = { left: "←", right: "→", up: "↑", down: "↓" };
const DIRECTION_LABEL: Record<string, string> = { left: "Слева", right: "Справа", up: "Сверху", down: "Снизу" };

type Phase = "idle" | "playing" | "result";

export function TrainingDummyPage() {
  const startDummy = useStartDummy();
  const completeDummy = useCompleteDummy();

  const [phase, setPhase] = useState<Phase>("idle");
  const [roundIndex, setRoundIndex] = useState(0);
  const [hits, setHits] = useState(0);
  const [answered, setAnswered] = useState(false);
  const [result, setResult] = useState<MinigameResultOut | null>(null);

  const start = startDummy.data;

  useEffect(() => {
    if (phase !== "playing" || !start) return;
    if (roundIndex >= start.directions.length) {
      completeDummy.mutate(
        { attemptId: start.attempt_id, hits },
        { onSuccess: (res) => { setResult(res); setPhase("result"); } },
      );
      return;
    }
    setAnswered(false);
    const timer = setTimeout(() => {
      setAnswered(true);
      setTimeout(() => setRoundIndex((n) => n + 1), 200);
    }, ROUND_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, roundIndex, start?.attempt_id]);

  function handleStart() {
    setResult(null);
    setRoundIndex(0);
    setHits(0);
    setAnswered(false);
    setPhase("idle");
    startDummy.mutate(undefined, { onSuccess: () => setPhase("playing") });
  }

  function handleTap(direction: string) {
    if (answered || !start) return;
    setAnswered(true);
    if (direction === start.directions[roundIndex]) setHits((h) => h + 1);
    setTimeout(() => setRoundIndex((n) => n + 1), 200);
  }

  const current = start && roundIndex < start.directions.length ? start.directions[roundIndex] : null;

  return (
    <div className="pb-6">
      <ScreenHeader title="Боевой манекен" />
      <div className="px-4">
        {phase === "idle" && (
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <span className="text-4xl" aria-hidden>
              ⚔️
            </span>
            <p className="font-mono text-[12px] text-ink-dim">
              Направление удара появится на манекене — быстро нажмите нужную сторону.
            </p>
            {startDummy.isError && <ErrorState error={startDummy.error} />}
            <Button className="w-full" disabled={startDummy.isPending} onClick={handleStart}>
              {startDummy.isPending ? "..." : "Начать"}
            </Button>
          </div>
        )}

        {phase === "playing" && start && current && (
          <div className="flex flex-col items-center gap-6 py-6">
            <p className="font-mono text-[11px] text-ink-dim">
              Раунд {roundIndex + 1} / {start.directions.length} · Попаданий: {hits}
            </p>
            <div className="flex h-28 w-28 items-center justify-center rounded-full border-2 border-ember bg-ember/10 text-5xl">
              {DIRECTION_ARROW[current]}
            </div>
            <div className="grid w-full max-w-xs grid-cols-3 gap-2">
              <div />
              <button
                onClick={() => handleTap("up")}
                disabled={answered}
                className="rounded-lg border border-hairline bg-bg-raised py-4 text-2xl active:bg-bg-raised-hover disabled:opacity-40"
              >
                ↑
              </button>
              <div />
              <button
                onClick={() => handleTap("left")}
                disabled={answered}
                className="rounded-lg border border-hairline bg-bg-raised py-4 text-2xl active:bg-bg-raised-hover disabled:opacity-40"
              >
                ←
              </button>
              <button
                onClick={() => handleTap("down")}
                disabled={answered}
                className="rounded-lg border border-hairline bg-bg-raised py-4 text-2xl active:bg-bg-raised-hover disabled:opacity-40"
              >
                ↓
              </button>
              <button
                onClick={() => handleTap("right")}
                disabled={answered}
                className="rounded-lg border border-hairline bg-bg-raised py-4 text-2xl active:bg-bg-raised-hover disabled:opacity-40"
              >
                →
              </button>
            </div>
            <p className="font-mono text-[10px] uppercase text-ink-dim">{DIRECTION_LABEL[current]}</p>
          </div>
        )}

        {phase === "result" && result && (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <p
              className={`font-mono text-[11px] uppercase tracking-wide ${
                result.success ? "text-iron-teal-bright" : "text-ink-dim"
              }`}
            >
              {result.success ? "Идеально" : "Тренировка окончена"}
            </p>
            <h2 className="font-display text-2xl font-semibold text-ink">Попаданий: {hits}</h2>
            {(result.reward_xp > 0 || result.reward_coins > 0) && (
              <div className="flex w-full gap-1.5">
                <div className="flex-1 rounded-md border border-hairline bg-bg-raised py-2.5 text-center">
                  <span className="block font-mono text-[13px] font-bold text-ink">+{formatNumber(result.reward_xp)}</span>
                  <span className="block font-mono text-[9px] uppercase text-ink-dim">XP</span>
                </div>
                <div className="flex-1 rounded-md border border-hairline bg-bg-raised py-2.5 text-center">
                  <span className="block font-mono text-[13px] font-bold text-ink">+{formatNumber(result.reward_coins)}</span>
                  <span className="block font-mono text-[9px] uppercase text-ink-dim">⏣</span>
                </div>
              </div>
            )}
            <Button className="w-full" onClick={handleStart}>
              Играть снова
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
