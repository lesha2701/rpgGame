"""Stage 11 leaderboards — no new tables, no new columns. Adds exactly one
index: `arena_matches.winner_user_id`, which the arena_wins leaderboard's
`GROUP BY` directly needs and which no existing index covers (the two
existing indexes on this table are on player_a_user_id/player_b_user_id,
neither of which the arena wins query filters or groups by). See
ARCHITECTURE.md's Stage 11 section for why every other leaderboard/profile
query was evaluated and found not to need a new index at this stage's
scale — this is not a "add indexes everywhere" migration.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-22

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_arena_matches_winner_user_id", "arena_matches", ["winner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_arena_matches_winner_user_id", table_name="arena_matches")
