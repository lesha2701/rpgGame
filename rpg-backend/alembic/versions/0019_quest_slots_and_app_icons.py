"""Quest slot rotation (UserQuest.slot_index + partial unique index) and
app_icons (admin-uploadable icons for the bottom nav / Battle hub rows /
More page rows, replacing hardcoded emoji).

Data backfill: every user's existing unclaimed UserQuest rows (from
before rotation existed, where every active QuestDefinition was always
assigned) are assigned into slots 0..ACTIVE_QUEST_SLOT_COUNT-1 in id
order; any beyond the slot count are deleted (they were never claimed, so
nothing is lost — they just re-enter the pool exactly like every other
not-yet-drawn definition). Already-claimed rows are untouched and keep
slot_index NULL, which is exactly correct: NULL + claimed_at set is
"history", the same shape a freshly-claimed row has going forward.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTIVE_QUEST_SLOT_COUNT = 5


def upgrade() -> None:
    op.execute("ALTER TYPE quest_condition_type ADD VALUE IF NOT EXISTS 'arena_wins'")
    op.execute("ALTER TYPE quest_condition_type ADD VALUE IF NOT EXISTS 'campaign_nodes_cleared'")

    op.add_column("user_quests", sa.Column("slot_index", sa.Integer(), nullable=True))

    # Backfill: rank each user's unclaimed rows by id, slot the first
    # ACTIVE_QUEST_SLOT_COUNT, drop the rest (never claimed, so no reward
    # was ever at stake).
    op.execute(
        f"""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY id) AS rn
            FROM user_quests
            WHERE claimed_at IS NULL
        )
        UPDATE user_quests
        SET slot_index = ranked.rn - 1
        FROM ranked
        WHERE user_quests.id = ranked.id AND ranked.rn <= {ACTIVE_QUEST_SLOT_COUNT}
        """
    )
    op.execute(
        f"""
        DELETE FROM user_quests
        WHERE claimed_at IS NULL
          AND id IN (
              SELECT id FROM (
                  SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY id) AS rn
                  FROM user_quests
                  WHERE claimed_at IS NULL
              ) ranked
              WHERE ranked.rn > {ACTIVE_QUEST_SLOT_COUNT}
          )
        """
    )

    op.create_index(
        "uq_user_quest_slot",
        "user_quests",
        ["user_id", "slot_index"],
        unique=True,
        postgresql_where=sa.text("slot_index IS NOT NULL"),
        sqlite_where=sa.text("slot_index IS NOT NULL"),
    )

    # --- app_icons ---
    op.create_table(
        "app_icons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("image_path", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("app_icons")
    op.drop_index("uq_user_quest_slot", table_name="user_quests")
    op.drop_column("user_quests", "slot_index")
    # The deleted never-claimed excess rows from the backfill are not
    # restorable — same accepted, documented limitation as every other
    # migration in this project with a one-way data backfill.
