import { ItemArtwork } from "@/components/artwork";
import { RARITY_TEXT_CLASS } from "@/components/artwork/rarity";
import type { UserItemOut } from "@/types";

interface ItemCardProps {
  userItem: UserItemOut;
  /** How many identical (same template, same equip state) copies this
   * card represents — stacked in the inventory grid instead of one card
   * per instance. Omit or pass 1 for a non-stacked card (e.g. Equipment). */
  count?: number;
  action?: { label: string; onClick: () => void; pending?: boolean };
  /** Opens the item detail sheet — separate from `action` (equip/unequip),
   * which stops propagation so tapping it doesn't also open the sheet. */
  onOpenDetail?: () => void;
}

export function ItemCard({ userItem, count, action, onOpenDetail }: ItemCardProps) {
  const template = userItem.item_template;
  return (
    <div
      role={onOpenDetail ? "button" : undefined}
      tabIndex={onOpenDetail ? 0 : undefined}
      onClick={onOpenDetail}
      className={`overflow-hidden rounded-lg border border-hairline bg-bg-surface text-left ${onOpenDetail ? "cursor-pointer" : ""}`}
    >
      <div className="relative">
        <ItemArtwork item={template} size="card" className="rounded-none" />
        <span className="absolute right-2 top-2 rounded bg-bg-base/70 px-1.5 py-0.5 font-mono text-[10px] font-bold text-ink backdrop-blur-sm">
          T{template.tier}
        </span>
        {userItem.is_equipped && (
          <span className="absolute left-2 top-2 rounded bg-iron-teal/80 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase text-[#0C1512]">
            Экипировано
          </span>
        )}
        {count !== undefined && count > 1 && (
          <span className="absolute bottom-2 right-2 rounded-full bg-bg-base/85 px-1.5 py-0.5 font-mono text-[10px] font-bold text-ember-bright backdrop-blur-sm">
            ×{count}
          </span>
        )}
      </div>
      <div className="p-2.5">
        <p className={`text-[12.5px] font-bold ${RARITY_TEXT_CLASS[template.rarity]}`}>{template.name}</p>
        <p className="mt-1 font-mono text-[10px] text-ink-dim">{template.slot}</p>
        {action && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              action.onClick();
            }}
            disabled={action.pending}
            className="mt-2 w-full rounded-md border border-hairline bg-bg-raised py-1.5 font-mono text-[10.5px] font-bold text-ink disabled:opacity-50"
          >
            {action.pending ? "..." : action.label}
          </button>
        )}
      </div>
    </div>
  );
}
