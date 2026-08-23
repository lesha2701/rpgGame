import { Link } from "react-router-dom";

import { ItemArtwork } from "@/components/artwork";
import { RARITY_TEXT_CLASS } from "@/components/artwork/rarity";
import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { ErrorState, Skeleton } from "@/components/ui";
import { useEquipment, useUnequipItem } from "@/hooks/useInventory";
import type { EquipmentSlot } from "@/types";

const SLOT_LABEL: Record<EquipmentSlot, string> = {
  weapon: "Оружие",
  helmet: "Шлем",
  armor: "Броня",
  boots: "Сапоги",
  gloves: "Перчатки",
  ring: "Кольцо",
  amulet: "Амулет",
};

const SLOT_ORDER: EquipmentSlot[] = ["weapon", "helmet", "armor", "boots", "gloves", "ring", "amulet"];

export function EquipmentPage() {
  const equipment = useEquipment();
  const unequip = useUnequipItem();

  if (equipment.isPending) {
    return (
      <div>
        <ScreenHeader title="Экипировка" />
        <div className="flex flex-col gap-2 px-4">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      </div>
    );
  }

  if (equipment.isError) {
    return (
      <div>
        <ScreenHeader title="Экипировка" />
        <div className="p-4">
          <ErrorState error={equipment.error} onRetry={() => equipment.refetch()} />
        </div>
      </div>
    );
  }

  return (
    <div className="pb-6">
      <ScreenHeader title="Экипировка" />
      <div className="flex flex-col gap-2 px-4">
        {SLOT_ORDER.map((slot) => {
          const item = equipment.data[slot];
          const template = item?.item_template;

          return (
            <div key={slot} className="flex items-center gap-3 rounded-lg border border-hairline bg-bg-surface p-2.5">
              {template ? (
                <ItemArtwork item={template} size="thumbnail" className="w-14" />
              ) : (
                <div className="flex h-14 w-14 flex-none items-center justify-center rounded-md border border-dashed border-hairline bg-bg-raised text-ink-dim">
                  +
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="font-mono text-[9.5px] uppercase tracking-wide text-ink-dim">{SLOT_LABEL[slot]}</p>
                <p className={`truncate text-[13px] font-bold ${template ? RARITY_TEXT_CLASS[template.rarity] : "text-ink-dim"}`}>
                  {template?.name ?? "Пусто"}
                </p>
              </div>
              {item ? (
                <button
                  onClick={() => unequip.mutate(item.id)}
                  disabled={unequip.isPending}
                  className="flex-none rounded-md border border-hairline bg-bg-raised px-3 py-1.5 font-mono text-[10.5px] font-bold text-ink disabled:opacity-50"
                >
                  Снять
                </button>
              ) : (
                <Link
                  to="/inventory"
                  className="flex-none rounded-md border border-hairline bg-bg-raised px-3 py-1.5 font-mono text-[10.5px] font-bold text-ink"
                >
                  Выбрать
                </Link>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
