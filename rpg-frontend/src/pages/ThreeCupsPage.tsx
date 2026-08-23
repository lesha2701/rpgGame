import { useEffect, useState } from "react";

import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { Button, ErrorState } from "@/components/ui";
import { useGuessCups, useStartCups } from "@/hooks/useMinigames";
import type { CupsRoundOut } from "@/types";
import { formatNumber } from "@/utils/format";

type Phase = "idle" | "shuffling" | "guessing" | "result";
const SHUFFLE_MS = 900;

export function ThreeCupsPage() {
  const startCups = useStartCups();
  const guessCups = useGuessCups();

  const [phase, setPhase] = useState<Phase>("idle");
  const [round, setRound] = useState<CupsRoundOut | null>(null);

  useEffect(() => {
    if (phase !== "shuffling") return;
    const timer = setTimeout(() => setPhase("guessing"), SHUFFLE_MS);
    return () => clearTimeout(timer);
  }, [phase]);

  function handleStart() {
    setPhase("idle");
    startCups.mutate(undefined, {
      onSuccess: (res) => {
        setRound(res);
        setPhase("shuffling");
      },
    });
  }

  function handleGuess(cup: number) {
    if (!round) return;
    guessCups.mutate(
      { attemptId: round.attempt_id, cup },
      {
        onSuccess: (res) => {
          setRound(res);
          setPhase(res.finished ? "result" : "shuffling");
        },
      },
    );
  }

  const shuffleSpeed = round ? Math.max(0.18, 0.42 - round.round * 0.05) : 0.42;

  return (
    <div className="pb-6">
      <ScreenHeader title="Три кубка" />
      <div className="px-4">
        {phase === "idle" && (
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <span className="text-4xl" aria-hidden>
              🪙
            </span>
            <p className="font-mono text-[12px] text-ink-dim">
              Монета под одним из кубков. Угадайте правильный — с каждым уровнем сложнее.
            </p>
            {startCups.isError && <ErrorState error={startCups.error} />}
            <Button className="w-full" disabled={startCups.isPending} onClick={handleStart}>
              {startCups.isPending ? "..." : "Начать"}
            </Button>
          </div>
        )}

        {(phase === "shuffling" || phase === "guessing") && round && (
          <div className="flex flex-col items-center gap-8 py-10">
            <p className="font-mono text-[11px] uppercase tracking-wide text-ink-dim">
              Уровень {round.round} / {round.max_rounds}
            </p>
            <div className="flex gap-4">
              {[0, 1, 2].map((cup) => (
                <button
                  key={cup}
                  onClick={() => handleGuess(cup)}
                  disabled={phase === "shuffling" || guessCups.isPending}
                  style={phase === "shuffling" ? { animationDuration: `${shuffleSpeed}s` } : undefined}
                  className={`flex h-24 w-20 items-center justify-center rounded-t-full border-2 border-ember bg-gradient-to-b from-ember-bright to-ember text-3xl shadow-glow-ember disabled:opacity-90 ${
                    phase === "shuffling" ? "animate-chest-shake" : ""
                  }`}
                  aria-label={`Кубок ${cup + 1}`}
                >
                  🍯
                </button>
              ))}
            </div>
            <p className="font-mono text-[10.5px] text-ink-dim">
              {phase === "shuffling" ? "Перемешиваем..." : "Выберите кубок"}
            </p>
            {guessCups.isError && <ErrorState error={guessCups.error} />}
          </div>
        )}

        {phase === "result" && round && (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <p
              className={`font-mono text-[11px] uppercase tracking-wide ${
                round.correct ? "text-iron-teal-bright" : "text-crimson-bright"
              }`}
            >
              {round.correct ? "Пройдено" : "Мимо"}
            </p>
            <h2 className="font-display text-2xl font-semibold text-ink">
              {round.correct ? `Все ${round.max_rounds} уровней пройдены!` : `Дошли до уровня ${round.round}`}
            </h2>
            {(round.reward_xp > 0 || round.reward_coins > 0) && (
              <div className="flex w-full gap-1.5">
                <div className="flex-1 rounded-md border border-hairline bg-bg-raised py-2.5 text-center">
                  <span className="block font-mono text-[13px] font-bold text-ink">+{formatNumber(round.reward_xp)}</span>
                  <span className="block font-mono text-[9px] uppercase text-ink-dim">XP</span>
                </div>
                <div className="flex-1 rounded-md border border-hairline bg-bg-raised py-2.5 text-center">
                  <span className="block font-mono text-[13px] font-bold text-ink">+{formatNumber(round.reward_coins)}</span>
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
