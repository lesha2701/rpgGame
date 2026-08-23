"""minigame_attempts + per-game attempt-limit columns on users — Memory
Sequence and Find the Pair, the first two mini-games under the
restructured Battle hub (see MinigameAttempt/User docstrings and
services/minigame_limits_service.py).

Revision ID: 0015
Revises: 0014
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Both brand new, used exactly once each (minigame_attempts.game_type/
# .status) — same "plain auto-creating Enum is fine for a single-use type"
# precedent as 0009's arena_match_status.
minigame_type_enum = sa.Enum("memory", "pairs", name="minigame_type")
minigame_attempt_status_enum = sa.Enum("pending", "completed", name="minigame_attempt_status")


def upgrade() -> None:
    # transaction_type already exists — adding a new member needs its own
    # ALTER TYPE, same gotcha as every prior migration that added one.
    op.execute("ALTER TYPE transaction_type ADD VALUE IF NOT EXISTS 'minigame_reward'")

    op.create_table(
        "minigame_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_type", minigame_type_enum, nullable=False),
        sa.Column("status", minigame_attempt_status_enum, nullable=False, server_default="pending"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("reward_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reward_coins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_minigame_attempts_user_id", "minigame_attempts", ["user_id"])

    for game in ("memory", "pairs"):
        op.add_column("users", sa.Column(f"{game}_hourly_attempts", sa.Integer(), nullable=False, server_default="0"))
        op.add_column("users", sa.Column(f"{game}_hour_started_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(
            "users", sa.Column(f"{game}_rewarded_attempts_today", sa.Integer(), nullable=False, server_default="0")
        )
        op.add_column("users", sa.Column(f"{game}_attempts_reset_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for game in ("memory", "pairs"):
        op.drop_column("users", f"{game}_attempts_reset_at")
        op.drop_column("users", f"{game}_rewarded_attempts_today")
        op.drop_column("users", f"{game}_hour_started_at")
        op.drop_column("users", f"{game}_hourly_attempts")

    op.drop_index("ix_minigame_attempts_user_id", "minigame_attempts")
    op.drop_table("minigame_attempts")
    minigame_attempt_status_enum.drop(op.get_bind(), checkfirst=True)
    minigame_type_enum.drop(op.get_bind(), checkfirst=True)
    # No ALTER TYPE ... DROP VALUE in Postgres — same limitation documented
    # on every other migration that added a transaction_type value.
