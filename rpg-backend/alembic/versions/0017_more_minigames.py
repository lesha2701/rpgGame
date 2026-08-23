"""Extends MinigameType with the four new mini-games (Training Dummy,
Alchemy, Tavern Dice, Three Cups) and adds their per-game hourly/daily
attempt-limit columns on users — same 4-column-per-game shape as memory/
pairs from migration 0015 (see User model's docstring).

Revision ID: 0017
Revises: 0016
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_GAMES = ("dummy", "alchemy", "dice", "cups")


def upgrade() -> None:
    for game in _NEW_GAMES:
        op.execute(f"ALTER TYPE minigame_type ADD VALUE IF NOT EXISTS '{game}'")

    for game in _NEW_GAMES:
        op.add_column("users", sa.Column(f"{game}_hourly_attempts", sa.Integer(), nullable=False, server_default="0"))
        op.add_column("users", sa.Column(f"{game}_hour_started_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(
            "users", sa.Column(f"{game}_rewarded_attempts_today", sa.Integer(), nullable=False, server_default="0")
        )
        op.add_column("users", sa.Column(f"{game}_attempts_reset_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for game in _NEW_GAMES:
        op.drop_column("users", f"{game}_attempts_reset_at")
        op.drop_column("users", f"{game}_rewarded_attempts_today")
        op.drop_column("users", f"{game}_hour_started_at")
        op.drop_column("users", f"{game}_hourly_attempts")
    # No ALTER TYPE ... DROP VALUE in Postgres — same limitation documented
    # on every other migration that added an enum value.
