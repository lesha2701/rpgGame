import { useQuery } from "@tanstack/react-query";

import { ImageUploadField } from "@/components/admin/ImageUploadField";
import { adminAppIconsApi } from "@/services/api";
import type { AppIconAdminOut } from "@/types";

const GROUP_LABEL: Record<string, string> = {
  nav: "Нижнее меню",
  mode: "Битвы — режимы",
  minigame: "Битвы — мини-игры",
  more: "Раздел «Ещё»",
};

function groupOf(key: string): string {
  return key.split("_")[0];
}

export function AdminAppIconsPage() {
  const icons = useQuery({ queryKey: ["admin", "app-icons"], queryFn: adminAppIconsApi.getAllAppIconsAdmin });

  const groups = new Map<string, AppIconAdminOut[]>();
  for (const icon of icons.data ?? []) {
    const g = groupOf(icon.key);
    groups.set(g, [...(groups.get(g) ?? []), icon]);
  }

  return (
    <div>
      <h1 className="mb-1 font-display text-2xl font-semibold text-ink">Иконки интерфейса</h1>
      <p className="mb-6 text-[13px] text-ink-mute">
        Загрузите изображения для нижнего меню, режимов и мини-игр раздела «Битвы» и пунктов раздела «Ещё» — они
        заменяют системные значки-заглушки. Набор слотов фиксирован и не редактируется здесь; заменить можно только
        картинку.
      </p>

      {icons.isPending && <p className="text-[13px] text-ink-mute">Загрузка...</p>}

      <div className="flex flex-col gap-8">
        {Array.from(groups.entries()).map(([group, items]) => (
          <div key={group}>
            <h2 className="mb-3 font-mono text-[11px] uppercase tracking-wide text-ink-dim">
              {GROUP_LABEL[group] ?? group}
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {items?.map((icon) => (
                <div key={icon.id} className="rounded-lg border border-hairline bg-bg-surface p-4">
                  <p className="mb-3 text-[13px] font-bold text-ink">{icon.label}</p>
                  <ImageUploadField
                    basePath="/admin/app-icons"
                    resourceId={icon.id}
                    currentImagePath={icon.image_path}
                    queryKey="app-icons"
                  />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
