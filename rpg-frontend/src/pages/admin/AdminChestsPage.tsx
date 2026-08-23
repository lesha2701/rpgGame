import { Link } from "react-router-dom";

import { ErrorState, Skeleton } from "@/components/ui";
import { useAdminChests, useToggleChestActive } from "@/hooks/useAdminChests";
import { formatNumber } from "@/utils/format";

export function AdminChestsPage() {
  const chests = useAdminChests();
  const toggle = useToggleChestActive();

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="font-display text-2xl font-semibold text-ink">Сундуки</h1>
        <Link
          to="/admin/chests/new"
          className="rounded-md bg-gradient-to-b from-ember-bright to-ember px-4 py-2 font-mono text-[12px] font-bold text-[#1D1204]"
        >
          + Создать
        </Link>
      </div>

      {chests.isPending && (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      )}
      {chests.isError && <ErrorState error={chests.error} onRetry={() => chests.refetch()} />}

      {chests.data && (
        <div className="overflow-x-auto rounded-lg border border-hairline">
          <table className="w-full min-w-[640px] text-left text-[12.5px]">
            <thead>
              <tr className="border-b border-hairline bg-bg-surface text-[10px] uppercase tracking-wide text-ink-dim">
                <th className="px-3 py-2">Название</th>
                <th className="px-3 py-2">Slug</th>
                <th className="px-3 py-2">Цена</th>
                <th className="px-3 py-2">Статус</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {chests.data
                .slice()
                .sort((a, b) => a.price - b.price)
                .map((c) => (
                  <tr key={c.id} className="border-b border-hairline last:border-none">
                    <td className="px-3 py-2 font-bold text-ink">{c.name}</td>
                    <td className="px-3 py-2 font-mono text-ink-dim">{c.slug}</td>
                    <td className="px-3 py-2 font-mono">{formatNumber(c.price)} ⏣</td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold ${
                          c.is_active ? "bg-iron-teal/15 text-iron-teal-bright" : "bg-crimson/15 text-crimson-bright"
                        }`}
                      >
                        {c.is_active ? "активен" : "выключен"}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => toggle.mutate(c.id)}
                          disabled={toggle.isPending}
                          className="rounded-md border border-hairline bg-bg-raised px-2.5 py-1 font-mono text-[10.5px] text-ink disabled:opacity-50"
                        >
                          {c.is_active ? "Выключить" : "Включить"}
                        </button>
                        <Link
                          to={`/admin/chests/${c.id}/edit`}
                          className="rounded-md border border-hairline bg-bg-raised px-2.5 py-1 font-mono text-[10.5px] text-ink"
                        >
                          Изменить
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
