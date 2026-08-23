"""expedition_templates (catalog) and user_expeditions (timestamp-driven,
no background worker — see UserExpedition/ExpeditionStatus docstrings and
ARCHITECTURE.md's Stage 7 section)

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# expedition_status is brand new and used exactly once (user_expeditions.
# status) — a plain auto-creating Enum is fine, same as 0006's battle_result.
expedition_status_enum = sa.Enum("running", "claimed", name="expedition_status")


def upgrade() -> None:
    # transaction_type already exists (created in 0005) — adding a new
    # member to an EXISTING enum needs its own ALTER TYPE, op.create_table()
    # only handles first-creation. Same gotcha as 0006's battle_reward; see
    # ARCHITECTURE.md's Stage 6 section for the full trace.
    op.execute("ALTER TYPE transaction_type ADD VALUE IF NOT EXISTS 'expedition_reward'")

    op.create_table(
        "expedition_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("required_hero_level", sa.Integer(), nullable=False),
        sa.Column("reward_xp", sa.Integer(), nullable=False),
        sa.Column("reward_coins", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_expedition_templates_required_hero_level", "expedition_templates", ["required_hero_level"])
    op.create_check_constraint(
        "ck_expedition_templates_duration_positive", "expedition_templates", "duration_seconds > 0"
    )
    op.create_check_constraint(
        "ck_expedition_templates_level_positive", "expedition_templates", "required_hero_level >= 1"
    )
    op.create_check_constraint(
        "ck_expedition_templates_reward_xp_non_negative", "expedition_templates", "reward_xp >= 0"
    )
    op.create_check_constraint(
        "ck_expedition_templates_reward_coins_non_negative", "expedition_templates", "reward_coins >= 0"
    )

    op.create_table(
        "user_expeditions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("hero_id", sa.Integer(), sa.ForeignKey("user_heroes.id"), nullable=False),
        sa.Column(
            "expedition_template_id", sa.Integer(), sa.ForeignKey("expedition_templates.id"), nullable=False
        ),
        sa.Column("status", expedition_status_enum, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reward_xp", sa.Integer(), nullable=False),
        sa.Column("reward_coins", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_expeditions_user_id", "user_expeditions", ["user_id"])
    op.create_index("ix_user_expeditions_hero_id", "user_expeditions", ["hero_id"])
    op.create_index(
        "ix_user_expeditions_expedition_template_id", "user_expeditions", ["expedition_template_id"]
    )
    op.create_check_constraint(
        "ck_user_expeditions_reward_xp_non_negative", "user_expeditions", "reward_xp >= 0"
    )
    op.create_check_constraint(
        "ck_user_expeditions_reward_coins_non_negative", "user_expeditions", "reward_coins >= 0"
    )
    # At most one RUNNING expedition per hero, at the DB level — see
    # UserExpedition's docstring for why this is defense-in-depth behind
    # the hero-row lock, not the primary correctness mechanism.
    op.create_index(
        "uq_user_expeditions_one_running_per_hero",
        "user_expeditions",
        ["hero_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
        sqlite_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_table("user_expeditions")
    op.drop_table("expedition_templates")
    expedition_status_enum.drop(op.get_bind(), checkfirst=True)
    # No ALTER TYPE ... DROP VALUE in Postgres — same limitation documented
    # on 0006's downgrade() for battle_reward. "expedition_reward" stays in
    # transaction_type's set of possible values even after this downgrade.
