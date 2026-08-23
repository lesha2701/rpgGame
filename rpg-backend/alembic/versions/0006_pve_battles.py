"""enemy_templates (PvE catalog) and battles (immutable fight records)

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# battle_result is brand new and used exactly once (battles.result) — a
# plain auto-creating Enum is fine here, same as 0003_skills.py's
# single-use skill_type. See ARCHITECTURE.md's "Alembic gotcha" section for
# when that's NOT sufficient (reusing a type across tables/migrations).
battle_result_enum = sa.Enum("won", "lost", name="battle_result")


def upgrade() -> None:
    # transaction_type was created in 0005 with only ("chest_purchase",
    # "admin_grant") — adding the "battle_reward" member Stage 6 needs
    # requires ALTER TYPE ... ADD VALUE (a plain op.create_table() only
    # auto-creates a type the FIRST time it's referenced; it does nothing
    # for an existing type that just needs another value). Safe to run
    # inside Alembic's transaction on Postgres 12+ as long as the new value
    # isn't used in that same transaction (it isn't — this migration only
    # adds it, nothing inserts a row with it).
    op.execute("ALTER TYPE transaction_type ADD VALUE IF NOT EXISTS 'battle_reward'")

    op.create_table(
        "enemy_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("hp", sa.Integer(), nullable=False),
        sa.Column("attack", sa.Integer(), nullable=False),
        sa.Column("defense", sa.Integer(), nullable=False),
        sa.Column("speed", sa.Integer(), nullable=False),
        sa.Column("crit_chance", sa.Numeric(5, 4), nullable=False, server_default="0.05"),
        sa.Column("crit_damage", sa.Numeric(5, 4), nullable=False, server_default="1.5"),
        sa.Column("reward_xp", sa.Integer(), nullable=False),
        sa.Column("reward_coins", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_enemy_templates_level", "enemy_templates", ["level"])
    op.create_check_constraint("ck_enemy_templates_level_positive", "enemy_templates", "level >= 1")
    op.create_check_constraint("ck_enemy_templates_hp_positive", "enemy_templates", "hp > 0")
    op.create_check_constraint(
        "ck_enemy_templates_reward_xp_non_negative", "enemy_templates", "reward_xp >= 0"
    )
    op.create_check_constraint(
        "ck_enemy_templates_reward_coins_non_negative", "enemy_templates", "reward_coins >= 0"
    )

    op.create_table(
        "battles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("hero_id", sa.Integer(), sa.ForeignKey("user_heroes.id"), nullable=False),
        sa.Column("enemy_template_id", sa.Integer(), sa.ForeignKey("enemy_templates.id"), nullable=False),
        sa.Column("result", battle_result_enum, nullable=False),
        sa.Column("turns", sa.Integer(), nullable=False),
        sa.Column("log", sa.JSON(), nullable=False),
        sa.Column("reward_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reward_coins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_battles_user_id", "battles", ["user_id"])
    op.create_index("ix_battles_hero_id", "battles", ["hero_id"])
    op.create_index("ix_battles_enemy_template_id", "battles", ["enemy_template_id"])
    op.create_index("ix_battles_idempotency_key", "battles", ["idempotency_key"])
    op.create_unique_constraint("uq_battle_idem", "battles", ["user_id", "idempotency_key"])
    op.create_check_constraint("ck_battles_turns_non_negative", "battles", "turns >= 0")
    op.create_check_constraint("ck_battles_reward_xp_non_negative", "battles", "reward_xp >= 0")
    op.create_check_constraint("ck_battles_reward_coins_non_negative", "battles", "reward_coins >= 0")


def downgrade() -> None:
    op.drop_table("battles")
    op.drop_table("enemy_templates")
    battle_result_enum.drop(op.get_bind(), checkfirst=True)
    # Postgres has no ALTER TYPE ... DROP VALUE — removing "battle_reward"
    # from transaction_type would require rebuilding the type from scratch
    # (new type, cast every existing row, swap, drop old type). Not done
    # here: no CoinTransaction row can reference it once the battles/
    # enemy_templates tables above are gone, and this migration has never
    # been downgraded in a real environment.
