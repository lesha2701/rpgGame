import { useState } from "react";
import { Link } from "react-router-dom";

import { ErrorState, Skeleton } from "@/components/ui";
import { useUserList, useUserStats } from "@/hooks/useAdminUsers";
import { formatNumber } from "@/utils/format";

function StatChip({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-hairline bg-bg-surface p-3">
      <p className="font-mono text-[9.5px] uppercase tracking-wide text-ink-dim">{label}</p>
      <p className="mt-1 font-display text-xl font-semibold text-ink">{formatNumber(value)}</p>
    </div>
  );
}

export function AdminUsersPage() {
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const stats = useUserStats();
  const list = useUserList(search, limit, offset);

  return (
    <div>
      <h1 className="mb-1 font-display text-2xl font-semibold text-ink">Пользователи</h1>
      <p className="mb-4 text-[12.5px] text-ink-mute">Поиск по username или Telegram ID, начисление монет, бан.</p>

      {stats.data && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <StatChip label="Всего" value={stats.data.total_users} />
          <StatChip label="С героем" value={stats.data.users_with_hero} />
          <StatChip label="Забанено" value={stats.data.banned_users} />
          <StatChip label="Админов" value={stats.data.admin_users} />
          <StatChip label="Монет в игре" value={stats.data.total_balance_in_circulation} />
        </div>
      )}

      <input
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setOffset(0);
        }}
        placeholder="Поиск по username или Telegram ID..."
        className="mb-4 w-full max-w-sm rounded-md border border-hairline bg-bg-raised px-3 py-2 text-[13px] text-ink outline-none"
      />

      {list.isPending && (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      )}
      {list.isError && <ErrorState error={list.error} onRetry={() => list.refetch()} />}

      {list.data && (
        <>
          <div className="overflow-x-auto rounded-lg border border-hairline">
            <table className="w-full min-w-[720px] text-left text-[12.5px]">
              <thead>
                <tr className="border-b border-hairline bg-bg-surface text-[10px] uppercase tracking-wide text-ink-dim">
                  <th className="px-3 py-2">Пользователь</th>
                  <th className="px-3 py-2">Telegram ID</th>
                  <th className="px-3 py-2">Герой</th>
                  <th className="px-3 py-2">Баланс</th>
                  <th className="px-3 py-2">Статус</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {list.data.users.map((u) => (
                  <tr key={u.id} className="border-b border-hairline last:border-none">
                    <td className="px-3 py-2 font-bold text-ink">{u.first_name ?? u.username ?? `#${u.id}`}</td>
                    <td className="px-3 py-2 font-mono text-ink-mute">{u.telegram_id}</td>
                    <td className="px-3 py-2 text-ink-mute">{u.hero_name ? `${u.hero_name} (${u.hero_level})` : "—"}</td>
                    <td className="px-3 py-2 font-mono text-ink-mute">{formatNumber(u.balance)} ⏣</td>
                    <td className="px-3 py-2">
                      {u.is_admin && (
                        <span className="mr-1 rounded bg-rarity-epic/15 px-2 py-0.5 font-mono text-[9.5px] font-bold text-rarity-epic">
                          admin
                        </span>
                      )}
                      {u.is_banned && (
                        <span className="rounded bg-crimson/15 px-2 py-0.5 font-mono text-[9.5px] font-bold text-crimson-bright">
                          забанен
                        </span>
                      )}
                      {!u.is_admin && !u.is_banned && <span className="text-ink-dim">—</span>}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Link
                        to={`/admin/users/${u.id}`}
                        className="rounded-md border border-hairline bg-bg-raised px-2.5 py-1 font-mono text-[10.5px] text-ink"
                      >
                        Открыть
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-3 flex items-center justify-between font-mono text-[11px] text-ink-dim">
            <span>
              {offset + 1}–{Math.min(offset + limit, list.data.total)} из {list.data.total}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setOffset(Math.max(0, offset - limit))}
                disabled={offset === 0}
                className="rounded-md border border-hairline bg-bg-raised px-3 py-1.5 disabled:opacity-40"
              >
                ← Назад
              </button>
              <button
                onClick={() => setOffset(offset + limit)}
                disabled={offset + limit >= list.data.total}
                className="rounded-md border border-hairline bg-bg-raised px-3 py-1.5 disabled:opacity-40"
              >
                Вперёд →
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
