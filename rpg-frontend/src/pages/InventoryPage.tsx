import { useMemo, useState, type ReactNode } from "react";

import { ItemCard } from "@/components/cards/ItemCard";
import { RARITY_LABEL } from "@/components/artwork/rarity";
import { ItemDetailSheet } from "@/components/inventory/ItemDetailSheet";
import { BalanceBar } from "@/components/layout/BalanceBar";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui";
import { useEquipItem, useInventory, useUnequipItem } from "@/hooks/useInventory";
import type { EquipmentSlot, Rarity, UserItemOut } from "@/types";

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
const RARITY_ORDER: Rarity[] = ["common", "rare", "epic", "legendary"];

interface InventoryStack {
  representative: UserItemOut;
  count: number;
}

/** Identical items (same template, same equip state) collapse into one
 * stacked card instead of N near-duplicate cards — grouping key is
 * template id + equip state, since at most one instance of a given
 * template can ever be equipped at once (equipped copies always end up
 * alone in their own group of 1). */
function groupStacks(items: UserItemOut[]): InventoryStack[] {
  const stacks = new Map<string, InventoryStack>();
  for (const item of items) {
    const key = `${item.item_template.id}:${item.is_equipped ? 1 : 0}`;
    const existing = stacks.get(key);
    if (existing) {
      existing.count += 1;
    } else {
      stacks.set(key, { representative: item, count: 1 });
    }
  }
  return Array.from(stacks.values());
}

function Select({
  value,
  onChange,
  children,
}: {
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="flex-1 rounded-md border border-hairline bg-bg-raised px-3 py-2 font-mono text-[11.5px] text-ink outline-none"
    >
      {children}
    </select>
  );
}

export function InventoryPage() {
  const inventory = useInventory();
  const equip = useEquipItem();
  const unequip = useUnequipItem();

  const [slotFilter, setSlotFilter] = useState<EquipmentSlot | "">("");
  const [rarityFilter, setRarityFilter] = useState<Rarity | "">("");
  const [detailItem, setDetailItem] = useState<UserItemOut | null>(null);

  const filtered = useMemo(() => {
    if (!inventory.data) return undefined;
    return inventory.data.filter((item) => {
      if (slotFilter && item.item_template.slot !== slotFilter) return false;
      if (rarityFilter && item.item_template.rarity !== rarityFilter) return false;
      return true;
    });
  }, [inventory.data, slotFilter, rarityFilter]);

  const stacks = useMemo(() => (filtered ? groupStacks(filtered) : undefined), [filtered]);

  return (
    <div>
      <BalanceBar />

      {inventory.data && inventory.data.length > 0 && (
        <div className="flex gap-2 px-4 pb-3">
          <Select value={slotFilter} onChange={(v) => setSlotFilter(v as EquipmentSlot | "")}>
            <option value="">Все слоты</option>
            {SLOT_ORDER.map((slot) => (
              <option key={slot} value={slot}>
                {SLOT_LABEL[slot]}
              </option>
            ))}
          </Select>
          <Select value={rarityFilter} onChange={(v) => setRarityFilter(v as Rarity | "")}>
            <option value="">Любая редкость</option>
            {RARITY_ORDER.map((rarity) => (
              <option key={rarity} value={rarity}>
                {RARITY_LABEL[rarity]}
              </option>
            ))}
          </Select>
        </div>
      )}

      <div className="px-4 pb-6">
        {inventory.isPending && (
          <div className="grid grid-cols-2 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="aspect-[3/4]" />
            ))}
          </div>
        )}

        {inventory.isError && <ErrorState error={inventory.error} onRetry={() => inventory.refetch()} />}

        {inventory.data?.length === 0 && (
          <EmptyState icon="🎒" title="Инвентарь пуст" description="Открывайте сундуки, чтобы получить предметы." />
        )}

        {stacks && stacks.length === 0 && inventory.data && inventory.data.length > 0 && (
          <EmptyState icon="🔍" title="Ничего не найдено" description="Попробуйте изменить фильтры." />
        )}

        {stacks && stacks.length > 0 && (
          <div className="grid grid-cols-2 gap-3">
            {stacks.map(({ representative: item, count }) => (
              <ItemCard
                key={`${item.item_template.id}:${item.is_equipped ? 1 : 0}`}
                userItem={item}
                count={count}
                onOpenDetail={() => setDetailItem(item)}
                action={
                  item.is_equipped
                    ? { label: "Снять", onClick: () => unequip.mutate(item.id), pending: unequip.isPending }
                    : { label: "Надеть", onClick: () => equip.mutate(item.id), pending: equip.isPending }
                }
              />
            ))}
          </div>
        )}
      </div>

      {detailItem && (
        <ItemDetailSheet
          userItem={detailItem}
          onClose={() => setDetailItem(null)}
          action={
            detailItem.is_equipped
              ? {
                  label: "Снять",
                  pending: unequip.isPending,
                  onClick: () => unequip.mutate(detailItem.id, { onSuccess: () => setDetailItem(null) }),
                }
              : {
                  label: "Надеть",
                  pending: equip.isPending,
                  onClick: () => equip.mutate(detailItem.id, { onSuccess: () => setDetailItem(null) }),
                }
          }
        />
      )}
    </div>
  );
}
