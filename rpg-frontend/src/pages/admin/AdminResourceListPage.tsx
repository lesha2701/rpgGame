import { Link, Navigate, useParams } from "react-router-dom";

import { ErrorState, Skeleton } from "@/components/ui";
import { RESOURCES } from "@/admin/resources";

function cellValue(row: Record<string, unknown>, key: string): string {
  const value = row[key];
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") {
    // nested race/character_class objects — display their `name`
    const nested = value as { name?: string };
    return nested.name ?? JSON.stringify(value);
  }
  if (typeof value === "boolean") return value ? "да" : "нет";
  return String(value);
}

export function AdminResourceListPage() {
  const { resource } = useParams<{ resource: string }>();
  const config = resource ? RESOURCES[resource] : undefined;

  if (!config) return <Navigate to="/admin/catalog" replace />;

  const list = config.hooks.useList();
  const toggle = config.hooks.useToggleActive();

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="font-display text-2xl font-semibold text-ink">{config.label}</h1>
        <Link
          to={`/admin/catalog/${config.key}/new`}
          className="rounded-md bg-gradient-to-b from-ember-bright to-ember px-4 py-2 font-mono text-[12px] font-bold text-[#1D1204]"
        >
          + Создать
        </Link>
      </div>

      {list.isPending && (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      )}
      {list.isError && <ErrorState error={list.error} onRetry={() => list.refetch()} />}

      {list.data && (
        <div className="overflow-x-auto rounded-lg border border-hairline">
          <table className="w-full min-w-[640px] text-left text-[12.5px]">
            <thead>
              <tr className="border-b border-hairline bg-bg-surface text-[10px] uppercase tracking-wide text-ink-dim">
                {config.columns.map((c) => (
                  <th key={c.key} className="px-3 py-2">
                    {c.label}
                  </th>
                ))}
                <th className="px-3 py-2">Статус</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {(list.data as Record<string, unknown>[])
                .slice()
                .sort((a, b) => ((a.sort_order as number) ?? 0) - ((b.sort_order as number) ?? 0))
                .map((row) => (
                  <tr key={row.id as number} className="border-b border-hairline last:border-none">
                    {config.columns.map((c) => (
                      <td key={c.key} className={`px-3 py-2 ${c.key === config.columns[0].key ? "font-bold text-ink" : "text-ink-mute"}`}>
                        {cellValue(row, c.key)}
                      </td>
                    ))}
                    <td className="px-3 py-2">
                      <span
                        className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold ${
                          row.is_active ? "bg-iron-teal/15 text-iron-teal-bright" : "bg-crimson/15 text-crimson-bright"
                        }`}
                      >
                        {row.is_active ? "активен" : "выключен"}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => toggle.mutate(row.id as number)}
                          disabled={toggle.isPending}
                          className="rounded-md border border-hairline bg-bg-raised px-2.5 py-1 font-mono text-[10.5px] text-ink disabled:opacity-50"
                        >
                          {row.is_active ? "Выключить" : "Включить"}
                        </button>
                        <Link
                          to={`/admin/catalog/${config.key}/${row.id}/edit`}
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
