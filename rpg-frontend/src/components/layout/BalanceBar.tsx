import { Pill, Skeleton } from "@/components/ui";
import { useMyProfile } from "@/hooks/useProfile";
import { formatNumber } from "@/utils/format";

/** Top bar for the bottom nav's own root screens (Сундуки/Битвы/Инвентарь/
 * Ещё) — no title, no back arrow (there's nowhere "back" to go from a nav
 * root, and the active nav tab already says where you are): just the
 * balance, same Pill treatment HeroPage already uses for its own overlay
 * bar. HeroPage keeps its bespoke absolutely-positioned version (full-bleed
 * art needs the bar layered on top, not in normal flow) — this is for the
 * other four, which don't have full-bleed background art. */
export function BalanceBar() {
  const profile = useMyProfile();
  return (
    <div className="flex items-center justify-end px-4 py-3">
      {profile.data ? (
        <Pill>
          <span className="h-1.5 w-1.5 rounded-full bg-rarity-legendary" />
          {formatNumber(profile.data.balance)}
        </Pill>
      ) : (
        <Skeleton className="h-[30px] w-[86px] rounded-full" />
      )}
    </div>
  );
}
