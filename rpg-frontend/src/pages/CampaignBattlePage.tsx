import { useNavigate, useParams } from "react-router-dom";

import { EnemyArtwork } from "@/components/artwork";
import { Button, ErrorState, Skeleton } from "@/components/ui";
import { useCampaignBattle, useSubmitCampaignAction } from "@/hooks/useCampaign";
import { useSession } from "@/hooks/useSession";
import type { BattleLogEntryOut, CampaignBattleOut, CampaignHeroStateOut } from "@/types";
import { formatNumber } from "@/utils/format";

const STATUS_LABEL_RU: Record<string, string> = {
  bleed: "Кровотечение",
  burn: "Ожог",
  frost: "Обморожение",
  poison: "Яд",
};

function statusLabelRu(label: string | null): string {
  if (!label) return "";
  return STATUS_LABEL_RU[label] ?? label;
}

function intentLine(intent: CampaignBattleOut["enemy"]["intent"]): string {
  if (!intent) return "";
  if (intent.skill_type === "damage" && intent.min_damage !== null && intent.max_damage !== null) {
    return intent.min_damage === intent.max_damage
      ? `${intent.name} — урон ${intent.min_damage}`
      : `${intent.name} — урон ${intent.min_damage}–${intent.max_damage}`;
  }
  if (intent.skill_type === "dot") return `${intent.name} — наносит ${statusLabelRu(intent.status_label)}`;
  if (intent.skill_type === "stun") return `${intent.name} — оглушает героя`;
  if (intent.skill_type === "shield") return `${intent.name} — укрепляет защиту`;
  if (intent.skill_type === "buff") return `${intent.name} — усиливает себя`;
  if (intent.skill_type === "debuff") return `${intent.name} — ослабляет героя`;
  return intent.name;
}

function logLine(entry: BattleLogEntryOut, enemyName: string): string {
  const who = (side: string) => (side === "hero" ? "Герой" : enemyName);
  switch (entry.action_type) {
    case "attack":
      return `${who(entry.attacker)} атакует ${who(entry.target)} → −${entry.damage}${entry.critical ? " (крит!)" : ""}`;
    case "skill":
      return `${who(entry.attacker)} применяет способность на ${who(entry.target)}${
        entry.damage > 0 ? ` → −${entry.damage}${entry.critical ? " (крит!)" : ""}` : ""
      }`;
    case "stunned":
      return `${who(entry.attacker)} оглушён и пропускает ход`;
    case "interrupted":
      return `Действие ${who(entry.attacker)} прервано`;
    case "dot_tick":
      return `${who(entry.attacker)} получает −${entry.damage} от эффекта`;
    case "defend":
      return `${who(entry.attacker)} занимает оборону`;
    case "item_effect": {
      const kind = (entry.status_effects[0]?.type as string) ?? "";
      if (kind === "lifesteal") return `Герой восполняет ${-entry.damage} HP от вампиризма`;
      if (kind === "shield_bonus") return `Экипировка укрепляет щит героя`;
      if (kind === "item_status") return `Экипировка накладывает эффект`;
      return `Срабатывает эффект экипировки`;
    }
    case "phase_transition":
      return (entry.status_effects[0]?.text as string) || `${enemyName} переходит в новую фазу боя`;
    case "stun_resisted":
      return `${who(entry.attacker)} устойчив к оглушению`;
    default:
      return `${who(entry.attacker)} действует`;
  }
}

function HeroStatusChips({ hero }: { hero: CampaignHeroStateOut }) {
  const chips: string[] = [];
  if (hero.stunned) chips.push("Оглушён");
  if (hero.shield_remaining > 0) chips.push(`Щит ${Math.round(hero.shield_remaining)}`);
  if (hero.dot_turns_remaining > 0) chips.push("Урон со временем");
  if (hero.buff_turns_remaining > 0) chips.push("Атака ↑");
  if (hero.defense_buff_turns_remaining > 0) chips.push("Защита ↑");
  if (!chips.length) return null;
  return (
    <div className="mt-1 flex flex-wrap gap-1">
      {chips.map((c) => (
        <span key={c} className="rounded-full border border-hairline bg-bg-raised px-2 py-0.5 font-mono text-[9px] text-ink-dim">
          {c}
        </span>
      ))}
    </div>
  );
}

export function CampaignBattlePage() {
  const { battleId } = useParams<{ battleId: string }>();
  const id = Number(battleId);
  const navigate = useNavigate();
  const battle = useCampaignBattle(id);
  const session = useSession();
  const submitAction = useSubmitCampaignAction(id);

  if (battle.isPending) {
    return (
      <div className="px-4 pt-4">
        <Skeleton className="h-64" />
        <Skeleton className="mt-3 h-40" />
      </div>
    );
  }

  if (battle.isError) {
    return (
      <div className="px-4 pt-4">
        <ErrorState error={battle.error} onRetry={() => battle.refetch()} />
      </div>
    );
  }

  const b = battle.data;
  const running = b.status === "running";
  const enemyPct = Math.max(0, (b.enemy.current_hp / b.enemy.max_hp) * 100);
  const heroPct = Math.max(0, (b.hero.current_hp / b.hero.max_hp) * 100);
  const canAct = running && !submitAction.isPending;

  function act(action_type: "basic_attack" | "skill" | "defend", skill_id?: number) {
    submitAction.mutate({ round: b.current_round, action_type, skill_id: skill_id ?? null });
  }

  return (
    <div className="flex flex-col pb-4">
      {/* Enemy artwork — dominant, ~40% of the screen (Stage 13 spec §14-20) */}
      <div className="relative h-[34vh] min-h-[230px] w-full overflow-hidden">
        <EnemyArtwork enemy={b.enemy} size="full-bleed" />
        <div className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-bg-base via-bg-base/70 to-transparent" />
        {b.enemy.is_boss && (
          <span className="absolute left-3 top-3 rounded-full border border-crimson/50 bg-bg-base/70 px-2.5 py-1 font-mono text-[9.5px] font-bold uppercase tracking-wide text-crimson-bright backdrop-blur-sm">
            Босс{b.enemy.phase_order ? ` · фаза ${b.enemy.phase_order}` : ""}
          </span>
        )}
        <button
          onClick={() => navigate("/campaign")}
          className="absolute right-3 top-3 rounded-full border border-hairline bg-bg-base/70 px-3 py-1.5 font-mono text-[11px] text-ink-mute backdrop-blur-sm"
        >
          ✕
        </button>
      </div>

      {/* Enemy info — name, HP, statuses, Intent */}
      <div className="px-4 pt-2">
        <div className="flex items-baseline justify-between">
          <p className="font-display text-lg font-semibold text-ink">{b.enemy.name}</p>
          <p className="font-mono text-[11px] text-ink-mute">
            {Math.round(b.enemy.current_hp)}/{b.enemy.max_hp}
          </p>
        </div>
        <div className="mt-1 h-2 overflow-hidden rounded-full bg-bg-raised">
          <div
            className="h-full rounded-full bg-gradient-to-r from-[#8A2E22] to-crimson-bright"
            style={{ width: `${enemyPct}%` }}
          />
        </div>
        <div className="mt-1 flex flex-wrap gap-1">
          {b.enemy.stunned && (
            <span className="rounded-full border border-hairline bg-bg-raised px-2 py-0.5 font-mono text-[9px] text-ink-dim">
              Оглушён
            </span>
          )}
          {b.enemy.shield_remaining > 0 && (
            <span className="rounded-full border border-hairline bg-bg-raised px-2 py-0.5 font-mono text-[9px] text-ink-dim">
              Щит {Math.round(b.enemy.shield_remaining)}
            </span>
          )}
          {b.enemy.dot_turns_remaining > 0 && (
            <span className="rounded-full border border-hairline bg-bg-raised px-2 py-0.5 font-mono text-[9px] text-ink-dim">
              Урон со временем
            </span>
          )}
        </div>

        {running && b.enemy.intent && (
          <div className="mt-2.5 rounded-md border border-hairline bg-bg-surface px-3 py-2">
            <p className="font-mono text-[9px] uppercase tracking-wide text-ink-dim">Следующее действие</p>
            <p className="mt-0.5 text-[12px] text-ink">{intentLine(b.enemy.intent)}</p>
          </div>
        )}
      </div>

      {/* Compact battle log — last few events only */}
      <div className="mt-3 px-4">
        <div className="flex flex-col gap-1">
          {b.log
            .slice()
            .reverse()
            .slice(0, 5)
            .map((entry, i) => (
              <div key={i} className="rounded border border-hairline bg-bg-surface px-2.5 py-1.5 text-[11px] text-ink-mute">
                {logLine(entry, b.enemy.name)}
              </div>
            ))}
        </div>
      </div>

      {/* Action area / Victory / Defeat */}
      <div className="sticky bottom-0 mt-3 bg-bg-base px-4 pt-1">
        {submitAction.isError && (
          <div className="mb-2">
            <ErrorState error={submitAction.error} />
          </div>
        )}

        {running && (
          <div className="grid grid-cols-2 gap-1.5">
            <Button variant="secondary" disabled={!canAct} onClick={() => act("basic_attack")}>
              Атака
            </Button>
            <Button variant="frost" disabled={!canAct} onClick={() => act("defend")}>
              Защита
            </Button>
            {b.hero.skills.map((s) => {
              const ready = s.cooldown_remaining <= 0;
              return (
                <div key={s.skill_definition_id} className="col-span-1">
                  <Button
                    variant="secondary"
                    disabled={!canAct || !ready}
                    onClick={() => act("skill", s.skill_definition_id)}
                    className="w-full"
                  >
                    {s.name}
                    {!ready && ` (${s.cooldown_remaining})`}
                  </Button>
                  {s.is_interrupt && ready && (
                    <p className="mt-0.5 text-center font-mono text-[9px] text-ink-dim">прерывает действие врага</p>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {!running && b.result === "won" && (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-hairline bg-bg-surface p-4 text-center">
            <p className="font-mono text-[12px] font-bold uppercase tracking-wide text-iron-teal-bright">Победа</p>
            <div className="flex w-full gap-1.5">
              <div className="flex-1 rounded-md border border-hairline bg-bg-raised py-2 text-center">
                <span className="block font-mono text-[13px] font-bold text-ink">+{formatNumber(b.reward_xp)}</span>
                <span className="block font-mono text-[9px] uppercase text-ink-dim">XP</span>
              </div>
              <div className="flex-1 rounded-md border border-hairline bg-bg-raised py-2 text-center">
                <span className="block font-mono text-[13px] font-bold text-ink">+{formatNumber(b.reward_coins)}</span>
                <span className="block font-mono text-[9px] uppercase text-ink-dim">⏣</span>
              </div>
            </div>
            <p className="font-mono text-[10px] text-ink-dim">
              {b.is_first_clear ? "Первое прохождение — полная награда" : "Повторное прохождение — часть награды"}
            </p>
            <Button className="w-full" onClick={() => navigate("/campaign")}>
              Продолжить путь
            </Button>
          </div>
        )}

        {!running && b.result === "lost" && (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-crimson/30 bg-bg-surface p-4 text-center">
            <p className="font-mono text-[12px] font-bold uppercase tracking-wide text-crimson-bright">Поражение</p>
            <p className="text-[12px] text-ink-mute">
              Герой пал в бою с «{b.enemy.name}» на {b.current_round}-м раунде.
            </p>
            <div className="flex w-full flex-col gap-1.5">
              <Button className="w-full" onClick={() => navigate(`/campaign/nodes/${b.node_id}`)}>
                Повторить
              </Button>
              <Button variant="secondary" className="w-full" onClick={() => navigate("/equipment")}>
                Изменить снаряжение
              </Button>
              <Button variant="ghost" className="w-full" onClick={() => navigate("/campaign")}>
                Вернуться к кампании
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Hero info — compact, no large art needed on this screen */}
      <div className="mt-3 flex items-center gap-3 px-4">
        <div className="flex-1">
          <div className="flex items-baseline justify-between">
            <p className="text-[12px] font-bold text-ink">{session.data?.user.active_hero?.hero_template.name ?? "Герой"}</p>
            <p className="font-mono text-[10.5px] text-ink-mute">
              {Math.round(b.hero.current_hp)}/{b.hero.max_hp}
            </p>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-bg-raised">
            <div
              className="h-full rounded-full bg-gradient-to-r from-iron-teal to-iron-teal-bright"
              style={{ width: `${heroPct}%` }}
            />
          </div>
          <HeroStatusChips hero={b.hero} />
        </div>
      </div>
    </div>
  );
}
