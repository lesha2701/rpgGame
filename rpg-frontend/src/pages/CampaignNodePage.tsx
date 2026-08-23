import { useNavigate, useParams } from "react-router-dom";

import { EnemyArtwork } from "@/components/artwork";
import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { Button, ErrorState, Skeleton, StatChip } from "@/components/ui";
import { useCampaignMap, useStartCampaignBattle } from "@/hooks/useCampaign";

const NODE_TYPE_LABEL: Record<string, string> = {
  battle: "Обычный бой",
  elite: "Элитный противник",
  boss: "Босс",
};

export function CampaignNodePage() {
  const { nodeId } = useParams<{ nodeId: string }>();
  const id = Number(nodeId);
  const navigate = useNavigate();
  const map = useCampaignMap();
  const startBattle = useStartCampaignBattle();

  if (map.isPending) {
    return (
      <div>
        <ScreenHeader title="Подготовка" />
        <div className="px-4">
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  if (map.isError) {
    return (
      <div>
        <ScreenHeader title="Подготовка" />
        <div className="px-4">
          <ErrorState error={map.error} onRetry={() => map.refetch()} />
        </div>
      </div>
    );
  }

  const node = map.data.regions.flatMap((r) => r.nodes).find((n) => n.id === id);
  if (!node) {
    return (
      <div>
        <ScreenHeader title="Подготовка" />
        <div className="px-4">
          <ErrorState error={new Error("Узел не найден")} />
        </div>
      </div>
    );
  }

  function start() {
    startBattle.mutate(
      { node_id: id },
      { onSuccess: (battle) => navigate(`/campaign/battles/${battle.id}`) },
    );
  }

  return (
    <div className="pb-6">
      <ScreenHeader title={node.name} />

      <div className="px-4">
        <EnemyArtwork
          enemy={{ name: node.enemy_name ?? node.name, image_path: node.enemy_image_path }}
          size="detail"
          className="w-full"
        />

        <div className="mt-3 flex gap-1.5">
          <StatChip value={NODE_TYPE_LABEL[node.node_type] ?? node.node_type} label="Тип" />
          <StatChip value={node.level} label="Уровень" />
          <StatChip value={node.clear_count} label="Побед" />
        </div>

        <div className="mt-3 rounded-md border border-hairline bg-bg-surface p-3">
          <p className="text-[13px] font-bold text-ink">{node.enemy_name}</p>
          {node.clear_count > 0 ? (
            <p className="mt-1 text-[11.5px] text-ink-mute">
              Этот узел уже пройден. Повторная награда — часть от полной (первое прохождение всегда полное).
            </p>
          ) : (
            <p className="mt-1 text-[11.5px] text-ink-mute">Первое прохождение приносит полную награду.</p>
          )}
        </div>

        {startBattle.isError && (
          <div className="mt-3">
            <ErrorState error={startBattle.error} />
          </div>
        )}

        {!node.available && (
          <p className="mt-4 text-center font-mono text-[11px] text-ink-dim">
            Этот узел пока недоступен — сначала пройдите предыдущие.
          </p>
        )}

        {node.available && (
          <Button className="mt-4 w-full" disabled={startBattle.isPending} onClick={start}>
            {startBattle.isPending ? "Начинаем..." : "В бой"}
          </Button>
        )}
      </div>
    </div>
  );
}
