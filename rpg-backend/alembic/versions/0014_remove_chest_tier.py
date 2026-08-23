"""Removes Chest.tier — a chest's reward tier is now capped by the
*opening hero's own* tier (equipment_tier_for_level(hero.level)), not by a
fixed tier on the chest itself; chests differ only by price/
rarity_probabilities/guaranteed_min_rarity now (see Chest's updated
docstring and chest_service.pick_random_item_template).

Data migration, scoped narrowly: only the chests seeded by app/seed.py's
_get_or_create_chest (slug LIKE 'tier-%-chest') and the free chest
(slug='free-chest') get renamed + reprobabilitied here — those are the
generic "Сундук N тира" placeholders whose name is now actively wrong
once tier is gone. Any OTHER chest (e.g. one an admin created by hand
through the admin panel) is left completely alone: only the tier column
itself goes away for those, name/probabilities untouched, since there's
no way to know an admin didn't intentionally customize them.

Revision ID: 0014
Revises: 0013
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Same escalating-odds formula for every seeded chest: t=0 at tier 1 (mostly
# common, a sliver of legendary) sliding to t=1 at tier 10 (mostly
# epic/legendary) — illustrative, admin-editable afterwards like everything
# else on Chest, not final tuning.
_SEEDED_NAMES = {
    1: "Простой сундук",
    2: "Крепкий сундук",
    3: "Добротный сундук",
    4: "Прочный сундук",
    5: "Ценный сундук",
    6: "Редкий сундук",
    7: "Изысканный сундук",
    8: "Роскошный сундук",
    9: "Королевский сундук",
    10: "Легендарный сундук",
}
_SEEDED_DESCRIPTION = "Содержит предмет экипировки — тир ограничен уровнем вашего героя."
_FREE_DESCRIPTION = "Доступен каждые 24 часа. Содержит предмет экипировки — тир ограничен уровнем вашего героя."


def _probabilities_for(tier: int) -> dict[str, float]:
    t = (max(1, min(tier, 10)) - 1) / 9
    common = round(0.70 + (0.05 - 0.70) * t, 4)
    legendary = round(0.01 + (0.35 - 0.01) * t, 4)
    epic = round(0.07 + (0.30 - 0.07) * t, 4)
    rare = round(1.0 - common - epic - legendary, 4)
    return {"common": common, "rare": rare, "epic": epic, "legendary": legendary}


def _upsert_probabilities(conn, chest_id: int, probabilities: dict[str, float]) -> None:
    for rarity, probability in probabilities.items():
        conn.execute(
            sa.text(
                """
                INSERT INTO chest_rarity_probabilities (chest_id, rarity, probability)
                VALUES (:chest_id, :rarity, :probability)
                ON CONFLICT (chest_id, rarity) DO UPDATE SET probability = EXCLUDED.probability
                """
            ),
            {"chest_id": chest_id, "rarity": rarity, "probability": probability},
        )


def upgrade() -> None:
    conn = op.get_bind()

    seeded = conn.execute(
        sa.text("SELECT id, tier FROM chests WHERE slug LIKE 'tier-%-chest'")
    ).fetchall()
    for row in seeded:
        name = _SEEDED_NAMES.get(row.tier, f"Сундук уровня {row.tier}")
        conn.execute(
            sa.text("UPDATE chests SET name = :name, description = :description WHERE id = :id"),
            {"name": name, "description": _SEEDED_DESCRIPTION, "id": row.id},
        )
        _upsert_probabilities(conn, row.id, _probabilities_for(row.tier))

    free_chest = conn.execute(sa.text("SELECT id FROM chests WHERE slug = 'free-chest'")).fetchone()
    if free_chest is not None:
        conn.execute(
            sa.text("UPDATE chests SET description = :description WHERE id = :id"),
            {"description": _FREE_DESCRIPTION, "id": free_chest.id},
        )
        _upsert_probabilities(conn, free_chest.id, _probabilities_for(1))

    op.drop_column("chests", "tier")


def downgrade() -> None:
    # Best-effort only: the column comes back, but renamed names and
    # rebalanced probabilities from upgrade() are not un-done (same
    # documented limitation as every other data-touching migration in this
    # project — see 0007/0013's downgrades).
    op.add_column("chests", sa.Column("tier", sa.Integer(), nullable=False, server_default="1"))
    op.alter_column("chests", "tier", server_default=None)
    op.create_check_constraint("ck_chests_tier_range", "chests", "tier >= 1 AND tier <= 10")
