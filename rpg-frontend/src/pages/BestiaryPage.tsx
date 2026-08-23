import { EnemyCard } from "@/components/cards/EnemyCard";
import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { ErrorState, Skeleton } from "@/components/ui";
import { useEnemies } from "@/hooks/useEnemies";

export function BestiaryPage() {
  const enemies = useEnemies();

  return (
    <div>
      <ScreenHeader title="Бестиарий" />
      <div className="grid grid-cols-2 gap-3 px-4 pb-6">
        {enemies.isPending &&
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="aspect-[3/4]" />)}
        {enemies.isError && (
          <div className="col-span-2">
            <ErrorState error={enemies.error} onRetry={() => enemies.refetch()} />
          </div>
        )}
        {enemies.data?.map((e) => <EnemyCard key={e.id} enemy={e} />)}
      </div>
    </div>
  );
}
