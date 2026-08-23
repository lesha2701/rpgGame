"""Read side of the campaign graph: region/node listing with per-user
`completed`/`available`/`is_current` computed at read time, and
`focus_node_id` (Stage 13 spec §12 — the map must open scrolled to the
player's current progress, never forcing a scroll from the very start
every time).

The only thing ever WRITTEN by application code for campaign progress is
UserCampaignNodeClear (see campaign_battle_service._record_node_clear) —
everything in this module is a pure derivation from that table plus the
CampaignNodeEdge graph, same "derive, don't store" principle as
ExpeditionStatus/ArenaMatchStatus elsewhere in this codebase."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_node import CampaignNode
from app.models.campaign_node_edge import CampaignNodeEdge
from app.models.campaign_region import CampaignRegion
from app.models.enemy_template import EnemyTemplate
from app.models.user_campaign_node_clear import UserCampaignNodeClear
from app.schemas.campaign import CampaignEdgeOut, CampaignMapOut, CampaignNodeOut, CampaignRegionOut


async def _fetch_graph(db: AsyncSession) -> tuple[list[CampaignRegion], list[CampaignNode], list[CampaignNodeEdge]]:
    regions = (
        (await db.execute(select(CampaignRegion).where(CampaignRegion.is_active.is_(True)).order_by(CampaignRegion.sort_order)))
        .scalars()
        .all()
    )
    nodes = (
        (
            await db.execute(
                select(CampaignNode).where(CampaignNode.is_active.is_(True)).order_by(CampaignNode.depth, CampaignNode.sort_order)
            )
        )
        .scalars()
        .all()
    )
    edges = (await db.execute(select(CampaignNodeEdge))).scalars().all()
    return list(regions), list(nodes), list(edges)


def _availability(
    nodes: list[CampaignNode], edges: list[CampaignNodeEdge], completed_node_ids: set[int]
) -> dict[int, bool]:
    """A node is available iff it's already completed (replayable, Stage 13
    spec §12), OR it has zero incoming edges (a region's entry point), OR
    at least one incoming edge's source node is completed — one uniform
    OR-rule covering both branch points (several nodes unlock from the
    same completed source) and merge points (a node with several
    incoming edges needs only ONE of them completed), no special-casing
    either shape."""
    incoming: dict[int, list[int]] = {node.id: [] for node in nodes}
    for edge in edges:
        if edge.to_node_id in incoming:
            incoming[edge.to_node_id].append(edge.from_node_id)

    available: dict[int, bool] = {}
    for node in nodes:
        sources = incoming[node.id]
        available[node.id] = (
            node.id in completed_node_ids or not sources or any(src in completed_node_ids for src in sources)
        )
    return available


def _focus_node_id(nodes: list[CampaignNode], available: dict[int, bool], completed_node_ids: set[int]) -> int | None:
    """The player's current point of progress: the earliest (by depth,
    then sort_order — the same ordering the map is rendered in) available-
    but-not-yet-completed node. Falls back to the furthest completed node
    if every available node is already cleared (a player who has cleared
    everything currently unlocked), and to the very first node if the
    player has no progress at all."""
    candidates = [n for n in nodes if available[n.id] and n.id not in completed_node_ids]
    if candidates:
        return candidates[0].id

    completed = [n for n in nodes if n.id in completed_node_ids]
    if completed:
        return completed[-1].id

    return nodes[0].id if nodes else None


async def get_campaign_map(db: AsyncSession, user_id: int) -> CampaignMapOut:
    regions, nodes, edges = await _fetch_graph(db)

    clears = (
        (await db.execute(select(UserCampaignNodeClear).where(UserCampaignNodeClear.user_id == user_id)))
        .scalars()
        .all()
    )
    clear_by_node = {c.node_id: c for c in clears}
    completed_node_ids = set(clear_by_node.keys())

    available = _availability(nodes, edges, completed_node_ids)
    focus_node_id = _focus_node_id(nodes, available, completed_node_ids)

    enemy_ids = {n.enemy_template_id for n in nodes if n.enemy_template_id is not None}
    enemies: dict[int, EnemyTemplate] = {}
    if enemy_ids:
        result = await db.execute(select(EnemyTemplate).where(EnemyTemplate.id.in_(enemy_ids)))
        enemies = {e.id: e for e in result.scalars().all()}

    nodes_by_region: dict[int, list[CampaignNodeOut]] = {r.id: [] for r in regions}
    for node in nodes:
        enemy = enemies.get(node.enemy_template_id) if node.enemy_template_id else None
        clear = clear_by_node.get(node.id)
        nodes_by_region.setdefault(node.region_id, []).append(
            CampaignNodeOut(
                id=node.id,
                region_id=node.region_id,
                code=node.code,
                name=node.name,
                node_type=node.node_type.value,
                enemy_template_id=node.enemy_template_id,
                enemy_name=enemy.name if enemy else None,
                enemy_image_path=enemy.image_path if enemy else None,
                enemy_level=enemy.level if enemy else None,
                level=node.level,
                depth=node.depth,
                sort_order=node.sort_order,
                completed=node.id in completed_node_ids,
                available=available[node.id],
                is_current=node.id == focus_node_id,
                clear_count=clear.clear_count if clear else 0,
            )
        )

    region_out = [
        CampaignRegionOut(
            id=r.id,
            code=r.code,
            name=r.name,
            description=r.description,
            image_path=r.image_path,
            sort_order=r.sort_order,
            nodes=nodes_by_region.get(r.id, []),
        )
        for r in regions
    ]

    return CampaignMapOut(
        regions=region_out,
        edges=[CampaignEdgeOut(from_node_id=e.from_node_id, to_node_id=e.to_node_id) for e in edges],
        focus_node_id=focus_node_id,
    )


async def is_node_available(db: AsyncSession, user_id: int, node: CampaignNode) -> bool:
    """Single-node availability check for campaign_battle_service.
    start_campaign_battle — same rule as get_campaign_map's per-node
    `available`, just scoped to one node instead of computing the whole
    graph's map (still needs the whole graph: a merge point's availability
    depends on its incoming edges' sources)."""
    _regions, nodes, edges = await _fetch_graph(db)
    clears = (
        (await db.execute(select(UserCampaignNodeClear.node_id).where(UserCampaignNodeClear.user_id == user_id)))
        .scalars()
        .all()
    )
    completed_node_ids = set(clears)
    available = _availability(nodes, edges, completed_node_ids)
    return available.get(node.id, False)
