import { Link } from "react-router-dom";

import { RESOURCE_LIST } from "@/admin/resources";

export function AdminCatalogPage() {
  return (
    <div>
      <h1 className="mb-1 font-display text-2xl font-semibold text-ink">Каталог</h1>
      <p className="mb-6 text-[12.5px] text-ink-mute">
        Полноценное редактирование — создание, изменение, включение/выключение. Жёсткого удаления нет (как и у
        сундуков) — деактивация им и является.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {RESOURCE_LIST.map((r) => (
          <Link
            key={r.key}
            to={`/admin/catalog/${r.key}`}
            className="rounded-lg border border-hairline bg-bg-surface p-4 hover:border-ember/50"
          >
            <p className="font-display text-lg font-semibold text-ink">{r.label}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
