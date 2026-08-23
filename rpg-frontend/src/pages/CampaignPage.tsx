import { useEffect, useRef, type Ref } from "react";
import { useNavigate } from "react-router-dom";

import { EnemyArtwork } from "@/components/artwork";
import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { ErrorState, Skeleton } from "@/components/ui";
import { useCampaignMap } from "@/hooks/useCampaign";
import type { CampaignNodeOut, CampaignRegionOut } from "@/types";

const NODE_TYPE_LABEL: Record<string, string> = {
  battle: "Бой",
  elite: "Элита",
  boss: "Босс",
  story_event: "Событие",
  treasure: "Сокровище",
  merchant: "Торговец",
  rest: "Отдых",
};

function nodeAccentClass(node: CampaignNodeOut): string {
  if (node.node_type === "boss") return "border-crimson/60";
  if (node.node_type === "elite") return "border-rarity-epic/60";
  if (node.is_current) return "border-iron-teal/60";
  return "border-hairline";
}

function NodeCard({ node, focusRef }: { node: CampaignNodeOut; focusRef?: Ref<HTMLDivElement> }) {
  const navigate = useNavigate();
  const locked = !node.available;

  return (
    <div ref={focusRef} className="w-[132px]">
      <button
        disabled={locked}
        onClick={() => navigate(`/campaign/nodes/${node.id}`)}
        className={`relative flex w-full flex-col items-center gap-1.5 rounded-lg border bg-bg-surface p-2 text-center disabled:opacity-45 ${nodeAccentClass(node)}`}
      >
        {node.completed && (
          <span className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-iron-teal-bright text-[10px] font-bold text-[#0C1512]">
            ✓
          </span>
        )}
        <EnemyArtwork
          enemy={{ name: node.enemy_name ?? node.name, image_path: node.enemy_image_path }}
          size="thumbnail"
          className="w-14"
        />
        <p className="line-clamp-1 text-[11.5px] font-bold text-ink">{node.name}</p>
        <p className="font-mono text-[9px] uppercase tracking-wide text-ink-dim">
          {NODE_TYPE_LABEL[node.node_type] ?? node.node_type} · ур. {node.level}
        </p>
        {locked && <p className="font-mono text-[9px] text-ink-dim">Недоступно</p>}
        {node.is_current && !node.completed && (
          <p className="font-mono text-[9px] font-bold text-iron-teal-bright">Сейчас здесь</p>
        )}
      </button>
    </div>
  );
}

function RegionSection({
  region,
  focusNodeId,
  focusRef,
}: {
  region: CampaignRegionOut;
  focusNodeId: number | null;
  focusRef: Ref<HTMLDivElement>;
}) {
  const depths = Array.from(new Set(region.nodes.map((n) => n.depth))).sort((a, b) => a - b);

  return (
    <section className="px-4 py-3">
      <p className="font-display text-base font-semibold text-ink">{region.name}</p>
      {region.description && <p className="mt-0.5 text-[11.5px] text-ink-mute">{region.description}</p>}

      <div className="mt-3 flex flex-col items-center">
        {depths.map((depth, i) => {
          const rowNodes = region.nodes
            .filter((n) => n.depth === depth)
            .sort((a, b) => a.sort_order - b.sort_order);
          return (
            <div key={depth} className="flex flex-col items-center">
              {i > 0 && <div className="h-4 w-0.5 bg-hairline" aria-hidden />}
              <div className="flex gap-2.5">
                {rowNodes.map((node) => (
                  <NodeCard key={node.id} node={node} focusRef={node.id === focusNodeId ? focusRef : undefined} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function CampaignPage() {
  const map = useCampaignMap();
  const focusRef = useRef<HTMLDivElement | null>(null);

  // Opening Campaign must land on the player's current progress, never
  // forcing a scroll through the whole chain from the start (Stage 13
  // spec §12) — the focus node's own ref, set inside whichever region
  // renders it, is what this scrolls to.
  useEffect(() => {
    if (map.data && focusRef.current) {
      focusRef.current.scrollIntoView({ block: "center" });
    }
  }, [map.data]);

  return (
    <div className="pb-6">
      <ScreenHeader title="Кампания" />

      {map.isPending && (
        <div className="flex flex-col gap-2 px-4">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      )}
      {map.isError && (
        <div className="px-4">
          <ErrorState error={map.error} onRetry={() => map.refetch()} />
        </div>
      )}

      {map.data?.regions.map((region) => (
        <RegionSection key={region.id} region={region} focusNodeId={map.data.focus_node_id} focusRef={focusRef} />
      ))}
    </div>
  );
}
