import { useEffect, useState } from "react";

import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { Button, ErrorState } from "@/components/ui";
import { useStartMemory, useSubmitMemory } from "@/hooks/useMinigames";
import type { MinigameResultOut } from "@/types";
import { formatNumber } from "@/utils/format";

const TILE_CLASS = [
  "bg-gradient-to-br from-ember-bright to-ember",
  "bg-gradient-to-br from-iron-teal-bright to-iron-teal",
  "bg-gradient-to-br from-crimson-bright to-crimson",
  "bg-gradient-to-br from-frost to-[#3A5C63]",
  "bg-gradient-to-br from-rarity-epic to-[#5F3A78]",
];

const STEP_MS = 650;
const GAP_MS = 250;

type Phase = "idle" | "watch" | "input" | "result";

function Tile({
  symbol,
  index,
  active,
  disabled,
  onClick,
}: {
  symbol: string;
  index: number;
  active: boolean;
  disabled: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`flex aspect-square flex-1 items-center justify-center rounded-xl text-3xl transition-all disabled:opacity-40 ${TILE_CLASS[index]} ${
        active ? "scale-105 ring-2 ring-ink" : "ring-1 ring-hairline"
      }`}
    >
      {symbol}
    </button>
  );
}

export function MemorySequencePage() {
  const startMemory = useStartMemory();
  const submitMemory = useSubmitMemory();

  const [phase, setPhase] = useState<Phase>("idle");
  const [watchIndex, setWatchIndex] = useState(-1);
  const [answer, setAnswer] = useState<number[]>([]);
  const [result, setResult] = useState<MinigameResultOut | null>(null);

  const start = startMemory.data;

  useEffect(() => {
    if (phase !== "watch" || !start) return;
    const sequence = start.sequence;
    let step = -1;
    const interval = setInterval(() => {
      step += 1;
      if (step >= sequence.length) {
        clearInterval(interval);
        setWatchIndex(-1);
        setPhase("input");
        return;
      }
      setWatchIndex(sequence[step]);
      setTimeout(() => setWatchIndex(-1), STEP_MS - GAP_MS);
    }, STEP_MS);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, start?.attempt_id]);

  function handleStart() {
    setResult(null);
    setAnswer([]);
    setPhase("idle");
    startMemory.mutate(undefined, {
      onSuccess: () => setPhase("watch"),
    });
  }

  function handleTap(index: number) {
    if (!start) return;
    const next = [...answer, index];
    setAnswer(next);
    if (next.length === start.sequence.length) {
      submitMemory.mutate(
        { attemptId: start.attempt_id, answer: next },
        { onSuccess: (res) => { setResult(res); setPhase("result"); } },
      );
    }
  }

  return (
    <div className="pb-6">
      <ScreenHeader title="Запомни последовательность" />
      <div className="px-4">
        {phase === "idle" && (
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <span className="text-4xl" aria-hidden>
              🧠
            </span>
            <p className="font-mono text-[12px] text-ink-dim">
              Запомните порядок символов, затем повторите его.
            </p>
            {startMemory.isError && <ErrorState error={startMemory.error} />}
            <Button className="w-full" disabled={startMemory.isPending} onClick={handleStart}>
              {startMemory.isPending ? "..." : "Начать"}
            </Button>
          </div>
        )}

        {(phase === "watch" || phase === "input") && start && (
          <div className="flex flex-col gap-6 py-6">
            <p className="text-center font-mono text-[11px] uppercase tracking-wide text-ink-dim">
              {phase === "watch" ? "Смотрите внимательно..." : "Повторите последовательность"}
            </p>
            <div className="flex gap-2.5">
              {start.symbols.map((symbol, i) => (
                <Tile
                  key={i}
                  symbol={symbol}
                  index={i}
                  active={watchIndex === i}
                  disabled={phase !== "input" || submitMemory.isPending}
                  onClick={() => handleTap(i)}
                />
              ))}
            </div>
            {phase === "input" && (
              <div className="flex justify-center gap-1.5">
                {start.sequence.map((_, i) => (
                  <span
                    key={i}
                    className={`h-2 w-2 rounded-full ${i < answer.length ? "bg-ember-bright" : "bg-bg-raised"}`}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {phase === "result" && result && (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <p
              className={`font-mono text-[11px] uppercase tracking-wide ${
                result.success ? "text-iron-teal-bright" : "text-crimson-bright"
              }`}
            >
              {result.success ? "Успех" : "Неверно"}
            </p>
            <h2 className="font-display text-2xl font-semibold text-ink">
              {result.success ? "Последовательность верна!" : "Не совпало"}
            </h2>
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
            {result.daily_rewarded_remaining === 0 && (
              <p className="font-mono text-[10.5px] text-ink-dim">
                Дневной лимит наград исчерпан — можно продолжать играть без награды.
              </p>
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
