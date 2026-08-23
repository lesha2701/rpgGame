import { useState } from "react";

import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { Button, ErrorState } from "@/components/ui";
import { useCompletePairs, useStartPairs } from "@/hooks/useMinigames";
import type { MinigameResultOut } from "@/types";
import { formatNumber } from "@/utils/format";

const MISMATCH_PAUSE_MS = 700;

type Phase = "idle" | "playing" | "result";

function Card({
  symbol,
  revealed,
  matched,
  onClick,
}: {
  symbol: string;
  revealed: boolean;
  matched: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={revealed || matched}
      className={`flex aspect-square items-center justify-center rounded-lg text-2xl transition-all ${
        matched
          ? "border border-iron-teal/50 bg-iron-teal/10 opacity-50"
          : revealed
            ? "border border-ember bg-ember/15"
            : "border border-hairline bg-bg-raised active:bg-bg-raised-hover"
      }`}
    >
      {revealed || matched ? symbol : ""}
    </button>
  );
}

export function FindPairsPage() {
  const startPairs = useStartPairs();
  const completePairs = useCompletePairs();

  const [phase, setPhase] = useState<Phase>("idle");
  const [flipped, setFlipped] = useState<number[]>([]);
  const [matched, setMatched] = useState<Set<number>>(new Set());
  const [moves, setMoves] = useState(0);
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<MinigameResultOut | null>(null);

  const start = startPairs.data;

  function handleStart() {
    setResult(null);
    setFlipped([]);
    setMatched(new Set());
    setMoves(0);
    setChecking(false);
    setPhase("idle");
    startPairs.mutate(undefined, { onSuccess: () => setPhase("playing") });
  }

  function handleFlip(index: number) {
    if (!start || checking || flipped.includes(index) || matched.has(index)) return;

    const next = [...flipped, index];
    setFlipped(next);
    if (next.length < 2) return;

    setChecking(true);
    const [a, b] = next;
    const isMatch = start.layout[a] === start.layout[b];
    const newMoves = moves + 1;
    setMoves(newMoves);

    setTimeout(() => {
      if (isMatch) {
        const nextMatched = new Set(matched);
        nextMatched.add(a);
        nextMatched.add(b);
        setMatched(nextMatched);
        setFlipped([]);
        setChecking(false);

        if (nextMatched.size === start.layout.length) {
          completePairs.mutate(
            { attemptId: start.attempt_id, moves: newMoves },
            { onSuccess: (res) => { setResult(res); setPhase("result"); } },
          );
        }
      } else {
        setFlipped([]);
        setChecking(false);
      }
    }, MISMATCH_PAUSE_MS);
  }

  return (
    <div className="pb-6">
      <ScreenHeader title="Найди пару" />
      <div className="px-4">
        {phase === "idle" && (
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <span className="text-4xl" aria-hidden>
              🃏
            </span>
            <p className="font-mono text-[12px] text-ink-dim">
              Находите одинаковые символы за наименьшее число ходов.
            </p>
            {startPairs.isError && <ErrorState error={startPairs.error} />}
            <Button className="w-full" disabled={startPairs.isPending} onClick={handleStart}>
              {startPairs.isPending ? "..." : "Начать"}
            </Button>
          </div>
        )}

        {phase === "playing" && start && (
          <div className="flex flex-col gap-4 py-4">
            <p className="text-center font-mono text-[11px] text-ink-dim">Ходов: {moves}</p>
            <div className="grid grid-cols-4 gap-2">
              {start.layout.map((pairId, i) => (
                <Card
                  key={i}
                  symbol={start.symbols[pairId]}
                  revealed={flipped.includes(i)}
                  matched={matched.has(i)}
                  onClick={() => handleFlip(i)}
                />
              ))}
            </div>
          </div>
        )}

        {phase === "result" && result && (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <p className="font-mono text-[11px] uppercase tracking-wide text-iron-teal-bright">Готово</p>
            <h2 className="font-display text-2xl font-semibold text-ink">
              Все пары найдены за {moves} {moves === 1 ? "ход" : "ходов"}
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
