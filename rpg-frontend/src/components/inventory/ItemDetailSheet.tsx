import { ItemArtwork } from "@/components/artwork";
import { RARITY_LABEL, RARITY_TEXT_CLASS } from "@/components/artwork/rarity";
import { StatChip } from "@/components/ui";
import type { EquipmentSlot, UserItemOut } from "@/types";

const SLOT_LABEL: Record<EquipmentSlot, string> = {
  weapon: "Оружие",
  helmet: "Шлем",
  armor: "Броня",
  boots: "Сапоги",
  gloves: "Перчатки",
  ring: "Кольцо",
  amulet: "Амулет",
};

const STAT_LABEL: Record<string, string> = {
  hp: "HP",
  attack: "Атака",
  defense: "Защита",
  speed: "Скорость",
};

interface ItemDetailSheetProps {
  userItem: UserItemOut;
  onClose: () => void;
  action?: { label: string; onClick: () => void; pending?: boolean };
}

export function ItemDetailSheet({ userItem, onClose, action }: ItemDetailSheetProps) {
  const t = userItem.item_template;
  const stats = Object.entries(t.stats).filter(([, value]) => value > 0);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-t-2xl border-t border-hairline bg-bg-surface p-4"
        style={{ paddingBottom: "calc(16px + var(--safe-bottom))" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-hairline" />

        <div className="flex gap-3">
          <ItemArtwork item={t} size="thumbnail" className="w-20 flex-none" />
          <div className="flex-1">
            <p className={`font-display text-base font-semibold ${RARITY_TEXT_CLASS[t.rarity]}`}>{t.name}</p>
            <p className="mt-0.5 font-mono text-[10.5px] text-ink-dim">
              {RARITY_LABEL[t.rarity]} · T{t.tier} · {SLOT_LABEL[t.slot as EquipmentSlot]}
            </p>
            {userItem.is_equipped && (
              <span className="mt-1.5 inline-block rounded bg-iron-teal/15 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase text-iron-teal-bright">
                Экипировано
              </span>
            )}
          </div>
        </div>

        {t.description && <p className="mt-3 text-[12.5px] text-ink-mute">{t.description}</p>}

        {stats.length > 0 && (
          <div className="mt-3 flex gap-1.5">
            {stats.map(([key, value]) => (
              <StatChip key={key} value={Math.round(value)} label={STAT_LABEL[key] ?? key} />
            ))}
          </div>
        )}

        {t.affixes.length > 0 && (
          <div className="mt-3">
            <p className="font-mono text-[10px] uppercase text-ink-dim">Аффиксы</p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {t.affixes.map((a) => (
                <span
                  key={a.id}
                  className="rounded-md border border-hairline bg-bg-raised px-2 py-1 font-mono text-[10.5px] text-ink"
                >
                  +{STAT_LABEL[a.stat_type] ?? a.stat_type}
                </span>
              ))}
            </div>
          </div>
        )}

        {action && (
          <button
            onClick={action.onClick}
            disabled={action.pending}
            className="mt-4 w-full rounded-md bg-gradient-to-b from-ember-bright to-ember py-2.5 font-mono text-[12px] font-bold text-[#1D1204] disabled:opacity-40"
          >
            {action.pending ? "..." : action.label}
          </button>
        )}
        <button
          onClick={onClose}
          className="mt-2 w-full rounded-md border border-hairline bg-bg-raised py-2.5 font-mono text-[12px] text-ink-mute"
        >
          Закрыть
        </button>
      </div>
    </div>
  );
}
