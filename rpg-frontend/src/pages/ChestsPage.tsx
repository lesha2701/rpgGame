import { ChestCard } from "@/components/cards/ChestCard";
import { BalanceBar } from "@/components/layout/BalanceBar";
import { ErrorState, Skeleton } from "@/components/ui";
import { useChests } from "@/hooks/useChests";

export function ChestsPage() {
  const chests = useChests();

  return (
    <div>
      <BalanceBar />
      <div className="grid grid-cols-2 gap-3 px-4 pb-6">
        {chests.isPending &&
          Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="aspect-[3/4]" />)}
        {chests.isError && (
          <div className="col-span-2">
            <ErrorState error={chests.error} onRetry={() => chests.refetch()} />
          </div>
        )}
        {/* Free chest first — "должен визуально выделяться" */}
        {chests.data
          ?.slice()
          .sort((a, b) => (a.slug === "free-chest" ? -1 : b.slug === "free-chest" ? 1 : a.price - b.price))
          .map((c) => <ChestCard key={c.id} chest={c} />)}
      </div>
    </div>
  );
}
