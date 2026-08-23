"""arena_matches — PvP, single stateful-then-frozen table (see
ArenaMatch/ArenaMatchStatus docstrings and ARCHITECTURE.md's Stage 9
section)

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# arena_match_status is brand new and used exactly once
# (arena_matches.status) — a plain auto-creating Enum is fine, same as
# 0006/0007/0008's single-use enums.
arena_match_status_enum = sa.Enum("running", "finished", name="arena_match_status")


def upgrade() -> None:
    # transaction_type already exists (created in 0005) — adding a new
    # member needs its own ALTER TYPE, applied proactively this time (see
    # ARCHITECTURE.md's Stage 6 section for the underlying gotcha, hit live
    # in Stage 6/7 and avoided in Stage 8/9 by doing this from the start).
    op.execute("ALTER TYPE transaction_type ADD VALUE IF NOT EXISTS 'arena_reward'")

    op.create_table(
        "arena_matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_a_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("player_a_hero_id", sa.Integer(), sa.ForeignKey("user_heroes.id"), nullable=False),
        sa.Column("player_b_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("player_b_hero_id", sa.Integer(), sa.ForeignKey("user_heroes.id"), nullable=False),
        sa.Column("status", arena_match_status_enum, nullable=False),
        sa.Column("current_round", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("log", sa.JSON(), nullable=False),
        sa.Column("round_deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("winner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reward_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reward_coins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_arena_matches_player_a_user_id", "arena_matches", ["player_a_user_id"])
    op.create_index("ix_arena_matches_player_a_hero_id", "arena_matches", ["player_a_hero_id"])
    op.create_index("ix_arena_matches_player_b_user_id", "arena_matches", ["player_b_user_id"])
    op.create_index("ix_arena_matches_player_b_hero_id", "arena_matches", ["player_b_hero_id"])

    op.create_check_constraint(
        "ck_arena_matches_distinct_heroes", "arena_matches", "player_a_hero_id != player_b_hero_id"
    )
    op.create_check_constraint("ck_arena_matches_round_positive", "arena_matches", "current_round >= 1")
    op.create_check_constraint(
        "ck_arena_matches_reward_xp_non_negative", "arena_matches", "reward_xp >= 0"
    )
    op.create_check_constraint(
        "ck_arena_matches_reward_coins_non_negative", "arena_matches", "reward_coins >= 0"
    )

    # Defense in depth, not the primary correctness mechanism — see
    # ArenaMatch's docstring for the honest limitation (doesn't cover a
    # hero being player_a in one running match and player_b in another).
    op.create_index(
        "uq_arena_matches_player_a_running",
        "arena_matches",
        ["player_a_hero_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
        sqlite_where=sa.text("status = 'running'"),
    )
    op.create_index(
        "uq_arena_matches_player_b_running",
        "arena_matches",
        ["player_b_hero_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
        sqlite_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_table("arena_matches")
    arena_match_status_enum.drop(op.get_bind(), checkfirst=True)
    # No ALTER TYPE ... DROP VALUE in Postgres — same limitation documented
    # on 0006/0007/0008's downgrade(). "arena_reward" stays in
    # transaction_type's set of possible values even after this downgrade.
