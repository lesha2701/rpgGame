"""quest_definitions (catalog) and user_quests (claim-only state — progress
is never stored, always computed live; see QuestDefinition/UserQuest
docstrings and ARCHITECTURE.md's Stage 8 section)

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# quest_condition_type is brand new and used exactly once
# (quest_definitions.condition_type) — a plain auto-creating Enum is fine,
# same as 0006's battle_result / 0007's expedition_status.
quest_condition_type_enum = sa.Enum(
    "battles_won",
    "expeditions_claimed",
    "chests_opened",
    "hero_level",
    "items_equipped",
    "skills_upgraded",
    name="quest_condition_type",
)


def upgrade() -> None:
    # transaction_type already exists (created in 0005) — adding a new
    # member to an EXISTING enum needs its own ALTER TYPE; op.create_table()
    # only handles first-creation of a type. Same gotcha as 0006's
    # battle_reward and 0007's expedition_reward — applied proactively this
    # time instead of being discovered live. See ARCHITECTURE.md's Stage 6
    # section for the full trace.
    op.execute("ALTER TYPE transaction_type ADD VALUE IF NOT EXISTS 'quest_reward'")

    op.create_table(
        "quest_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("condition_type", quest_condition_type_enum, nullable=False),
        sa.Column("target_value", sa.Integer(), nullable=False),
        sa.Column("reward_xp", sa.Integer(), nullable=False),
        sa.Column("reward_coins", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_check_constraint(
        "ck_quest_definitions_target_value_positive", "quest_definitions", "target_value > 0"
    )
    op.create_check_constraint(
        "ck_quest_definitions_reward_xp_non_negative", "quest_definitions", "reward_xp >= 0"
    )
    op.create_check_constraint(
        "ck_quest_definitions_reward_coins_non_negative", "quest_definitions", "reward_coins >= 0"
    )

    op.create_table(
        "user_quests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("quest_definition_id", sa.Integer(), sa.ForeignKey("quest_definitions.id"), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_quests_user_id", "user_quests", ["user_id"])
    op.create_index("ix_user_quests_quest_definition_id", "user_quests", ["quest_definition_id"])
    op.create_unique_constraint("uq_user_quest", "user_quests", ["user_id", "quest_definition_id"])


def downgrade() -> None:
    op.drop_table("user_quests")
    op.drop_table("quest_definitions")
    quest_condition_type_enum.drop(op.get_bind(), checkfirst=True)
    # No ALTER TYPE ... DROP VALUE in Postgres — same limitation documented
    # on 0006/0007's downgrade(). "quest_reward" stays in transaction_type's
    # set of possible values even after this downgrade.
