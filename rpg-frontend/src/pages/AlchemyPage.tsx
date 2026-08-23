import { useEffect, useState } from "react";

import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { Button, ErrorState } from "@/components/ui";
import { useStartAlchemy, useSubmitAlchemy } from "@/hooks/useMinigames";
import type { MinigameResultOut } from "@/types";
import { formatNumber } from "@/utils/format";

const MEMORIZE_MS = 3000;

type Phase = "idle" | "memorize" | "input" | "result";

export function AlchemyPage() {
  const startAlchemy = useStartAlchemy();
  const submitAlchemy = useSubmitAlchemy();

  const [phase, setPhase] = useState<Phase>("idle");
  const [cauldron, setCauldron] = useState<number[]>([]);
  const [result, setResult] = useState<MinigameResultOut | null>(null);

  const start = startAlchemy.data;

  useEffect(() => {
    if (phase !== "memorize") return;
    const timer = setTimeout(() => setPhase("input"), MEMORIZE_MS);
    return () => clearTimeout(timer);
  }, [phase]);

  function handleStart() {
    setResult(null);
    setCauldron([]);
    setPhase("idle");
    startAlchemy.mutate(undefined, { onSuccess: () => setPhase("memorize") });
  }

  function handleAddIngredient(index: number) {
    if (!start || cauldron.includes(index)) return;
    const next = [...cauldron, index];
    setCauldron(next);
    if (next.length === start.recipe.length) {
      submitAlchemy.mutate(
        { attemptId: start.attempt_id, answer: next },
        { onSuccess: (res) => { setResult(res); setPhase("result"); } },
      );
    }
  }

  return (
    <div className="pb-6">
      <ScreenHeader title="Алхимия" />
      <div className="px-4">
        {phase === "idle" && (
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <span className="text-4xl" aria-hidden>
              🧪
            </span>
            <p className="font-mono text-[12px] text-ink-dim">
              Запомните порядок рецепта, затем соберите ингредиенты в котле в том же порядке.
            </p>
            {startAlchemy.isError && <ErrorState error={startAlchemy.error} />}
            <Button className="w-full" disabled={startAlchemy.isPending} onClick={handleStart}>
              {startAlchemy.isPending ? "..." : "Начать"}
            </Button>
          </div>
        )}

        {phase === "memorize" && start && (
          <div className="flex flex-col items-center gap-4 py-8">
            <p className="font-mono text-[11px] uppercase tracking-wide text-ink-dim">Рецепт</p>
            <div className="flex flex-wrap justify-center gap-2.5">
              {start.recipe.map((ingredientIndex, i) => (
                <div
                  key={i}
                  className="flex h-14 w-14 items-center justify-center rounded-lg border border-hairline bg-bg-raised text-2xl"
                >
                  {start.ingredients[ingredientIndex]}
                </div>
              ))}
            </div>
            <p className="font-mono text-[10.5px] text-ink-dim">Запоминайте...</p>
          </div>
        )}

        {phase === "input" && start && (
          <div className="flex flex-col gap-6 py-6">
            <div className="flex flex-col items-center gap-2">
              <p className="font-mono text-[11px] uppercase tracking-wide text-ink-dim">Котёл</p>
              <div className="flex min-h-[56px] flex-wrap justify-center gap-1.5 rounded-lg border border-hairline bg-bg-surface p-2">
                {cauldron.length === 0 && (
                  <span className="py-3 font-mono text-[10.5px] text-ink-dim">Добавляйте ингредиенты по порядку</span>
                )}
                {cauldron.map((ingredientIndex, i) => (
                  <div
                    key={i}
                    className="flex h-10 w-10 items-center justify-center rounded-md bg-ember/15 text-xl"
                  >
                    {start.ingredients[ingredientIndex]}
                  </div>
                ))}
              </div>
            </div>

            <div>
              <p className="mb-2 text-center font-mono text-[10.5px] uppercase tracking-wide text-ink-dim">
                Ингредиенты на столе
              </p>
              <div className="grid grid-cols-3 gap-2.5">
                {start.ingredients.map((symbol, i) => (
                  <button
                    key={i}
                    onClick={() => handleAddIngredient(i)}
                    disabled={cauldron.includes(i) || submitAlchemy.isPending}
                    className="flex aspect-square items-center justify-center rounded-lg border border-hairline bg-bg-raised text-3xl disabled:opacity-30"
                  >
                    {symbol}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {phase === "result" && result && (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <p
              className={`font-mono text-[11px] uppercase tracking-wide ${
                result.success ? "text-iron-teal-bright" : "text-crimson-bright"
              }`}
            >
              {result.success ? "Зелье готово" : "Рецепт испорчен"}
            </p>
            <h2 className="font-display text-2xl font-semibold text-ink">
              {result.success ? "Порядок верный!" : "Не тот порядок"}
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
            <Button className="w-full" onClick={handleStart}>
              Играть снова
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
