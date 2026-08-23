import { useState } from "react";

import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { Button, ErrorState } from "@/components/ui";
import { useBankDice, useRollDice, useStartDice } from "@/hooks/useMinigames";
import type { DiceRoundOut } from "@/types";
import { formatNumber } from "@/utils/format";

const DICE_FACE: Record<number, string> = { 1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅" };

type Phase = "idle" | "playing" | "result";

export function TavernDicePage() {
  const startDice = useStartDice();
  const rollDice = useRollDice();
  const bankDice = useBankDice();

  const [phase, setPhase] = useState<Phase>("idle");
  const [round, setRound] = useState<DiceRoundOut | null>(null);

  function handleStart() {
    setPhase("idle");
    startDice.mutate(undefined, {
      onSuccess: (res) => {
        setRound(res);
        setPhase("playing");
      },
    });
  }

  function handleRoll() {
    if (!round) return;
    rollDice.mutate(round.attempt_id, {
      onSuccess: (res) => {
        setRound(res);
        if (res.finished) setPhase("result");
      },
    });
  }

  function handleBank() {
    if (!round) return;
    bankDice.mutate(round.attempt_id, {
      onSuccess: (res) => {
        setRound(res);
        setPhase("result");
      },
    });
  }

  const busy = rollDice.isPending || bankDice.isPending;

  return (
    <div className="pb-6">
      <ScreenHeader title="Тавернные кости" />
      <div className="px-4">
        {phase === "idle" && (
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <span className="text-4xl" aria-hidden>
              🍺
            </span>
            <p className="font-mono text-[12px] text-ink-dim">
              Бросайте кости и копите банк. Заберите выигрыш вовремя — или рискните и потеряйте всё.
            </p>
            {startDice.isError && <ErrorState error={startDice.error} />}
            <Button className="w-full" disabled={startDice.isPending} onClick={handleStart}>
              {startDice.isPending ? "..." : "Начать"}
            </Button>
          </div>
        )}

        {phase === "playing" && round && (
          <div className="flex flex-col items-center gap-6 py-8">
            <div className="text-6xl" aria-hidden>
              {round.roll ? DICE_FACE[round.roll] : "🎲"}
            </div>
            <div className="w-full rounded-lg border border-hairline bg-bg-surface py-4 text-center">
              <span className="block font-mono text-2xl font-bold text-ember-bright">{round.pot}</span>
              <span className="block font-mono text-[10px] uppercase text-ink-dim">Банк</span>
            </div>
            <p className="font-mono text-[10.5px] text-ink-dim">
              Бросков: {round.rolls_made} / {round.max_rolls} · выпадение 1 сжигает банк
            </p>
            {rollDice.isError && <ErrorState error={rollDice.error} />}
            <div className="flex w-full gap-2">
              <Button className="flex-1" variant="secondary" disabled={busy || round.pot === 0} onClick={handleBank}>
                {bankDice.isPending ? "..." : "Забрать"}
              </Button>
              <Button className="flex-1" disabled={busy} onClick={handleRoll}>
                {rollDice.isPending ? "..." : "Бросить"}
              </Button>
            </div>
          </div>
        )}

        {phase === "result" && round && (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <p
              className={`font-mono text-[11px] uppercase tracking-wide ${
                round.busted ? "text-crimson-bright" : "text-iron-teal-bright"
              }`}
            >
              {round.busted ? "Мимо!" : "Забрано"}
            </p>
            <h2 className="font-display text-2xl font-semibold text-ink">
              {round.busted ? "Банк потерян" : `Банк: ${round.pot}`}
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
