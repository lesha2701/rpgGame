import { useState } from "react";
import { useParams } from "react-router-dom";

import { ErrorState, Skeleton } from "@/components/ui";
import { useDeductCoins, useGrantCoins, useToggleBan, useUserDetail } from "@/hooks/useAdminUsers";
import { formatNumber } from "@/utils/format";

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-hairline bg-bg-raised px-3 py-2.5">
      <span className="block font-mono text-[13px] font-bold text-ink">{value}</span>
      <span className="block font-mono text-[9px] uppercase text-ink-dim">{label}</span>
    </div>
  );
}

export function AdminUserDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const id = Number(userId);
  const detail = useUserDetail(id);
  const grantCoins = useGrantCoins();
  const deductCoins = useDeductCoins();
  const toggleBan = useToggleBan();

  const [amount, setAmount] = useState("100");
  const [description, setDescription] = useState("");

  if (detail.isPending) return <Skeleton className="h-96" />;
  if (detail.isError) return <ErrorState error={detail.error} onRetry={() => detail.refetch()} />;

  const u = detail.data;
  const s = u.statistics;

  return (
    <div className="max-w-2xl">
      <h1 className="mb-1 font-display text-2xl font-semibold text-ink">
        {u.first_name ?? u.username ?? `#${u.id}`}
      </h1>
      <p className="mb-6 font-mono text-[11px] text-ink-dim">
        Telegram ID {u.telegram_id} · зарегистрирован {new Date(u.created_at).toLocaleDateString("ru-RU")}
        {u.hero_name && ` · ${u.hero_name}, уровень ${u.hero_level}`}
      </p>

      <div className="mb-6 flex flex-wrap gap-2">
        {u.is_admin && <span className="rounded bg-rarity-epic/15 px-2 py-1 font-mono text-[10px] font-bold text-rarity-epic">admin</span>}
        {u.is_banned && (
          <span className="rounded bg-crimson/15 px-2 py-1 font-mono text-[10px] font-bold text-crimson-bright">забанен</span>
        )}
      </div>

      <div className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Баланс" value={u.balance} />
        <Stat label="PvE побед" value={s.battles.wins} />
        <Stat label="Arena побед" value={s.arena.wins} />
        <Stat label="Экспедиций" value={s.expeditions.claimed} />
        <Stat label="Квестов" value={s.quests.claimed} />
        <Stat label="Сундуков" value={s.chests.opened} />
        <Stat label="Рефералов" value={s.referrals.referral_count} />
        <Stat label="Успешных реф." value={s.referrals.successful_referrals} />
      </div>

      <div className="mb-4 rounded-lg border border-hairline bg-bg-surface p-4">
        <p className="mb-3 font-mono text-[11px] font-bold text-ink">Начислить / списать монеты</p>
        {grantCoins.isError && <div className="mb-2"><ErrorState error={grantCoins.error} /></div>}
        {deductCoins.isError && <div className="mb-2"><ErrorState error={deductCoins.error} /></div>}
        <div className="flex flex-wrap gap-2">
          <input
            type="number"
            min={1}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-28 rounded-md border border-hairline bg-bg-raised px-3 py-2 font-mono text-[13px] text-ink outline-none"
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Причина (необязательно)"
            className="flex-1 rounded-md border border-hairline bg-bg-raised px-3 py-2 text-[13px] text-ink outline-none"
          />
          <button
            onClick={() => grantCoins.mutate({ id, amount: Number(amount), description })}
            disabled={grantCoins.isPending || deductCoins.isPending || Number(amount) <= 0}
            className="rounded-md bg-gradient-to-b from-ember-bright to-ember px-4 py-2 font-mono text-[12px] font-bold text-[#1D1204] disabled:opacity-40"
          >
            {grantCoins.isPending ? "..." : `+${formatNumber(Number(amount) || 0)} ⏣`}
          </button>
          <button
            onClick={() => deductCoins.mutate({ id, amount: Number(amount), description })}
            disabled={grantCoins.isPending || deductCoins.isPending || Number(amount) <= 0}
            className="rounded-md border border-crimson bg-crimson/15 px-4 py-2 font-mono text-[12px] font-bold text-crimson-bright disabled:opacity-40"
          >
            {deductCoins.isPending ? "..." : `-${formatNumber(Number(amount) || 0)} ⏣`}
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-hairline bg-bg-surface p-4">
        <p className="mb-3 font-mono text-[11px] font-bold text-ink">Модерация</p>
        {toggleBan.isError && <div className="mb-2"><ErrorState error={toggleBan.error} /></div>}
        <button
          onClick={() => toggleBan.mutate(id)}
          disabled={toggleBan.isPending || u.is_admin}
          className={`rounded-md border px-4 py-2 font-mono text-[12px] font-bold disabled:opacity-40 ${
            u.is_banned ? "border-iron-teal bg-iron-teal/15 text-iron-teal-bright" : "border-crimson bg-crimson/15 text-crimson-bright"
          }`}
        >
          {toggleBan.isPending ? "..." : u.is_banned ? "Разбанить" : "Забанить"}
        </button>
        {u.is_admin && <p className="mt-2 font-mono text-[10.5px] text-ink-dim">Нельзя забанить администратора.</p>}
      </div>
    </div>
  );
}
