"""character foundation: users, races, character_classes, hero_templates, user_heroes

Revision ID: 0001
Revises:
Create Date: 2026-08-21

This is the RPG's own, independent baseline — it does not build on and is
not compatible with the football app's 0001-0051 history. It must only ever
be run against the isolated rpg_game database (see alembic/env.py's guard
and docker-compose.rpg.yml).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default=sa.false()),
        # active_hero_id is added below via ALTER, once user_heroes exists.
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_users_telegram_id", "users", ["telegram_id"])
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    op.create_table(
        "races",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_races_code", "races", ["code"])

    op.create_table(
        "character_classes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("base_hp", sa.Integer(), nullable=False),
        sa.Column("base_attack", sa.Integer(), nullable=False),
        sa.Column("base_defense", sa.Integer(), nullable=False),
        sa.Column("base_speed", sa.Integer(), nullable=False),
        sa.Column("base_crit_chance", sa.Numeric(5, 4), nullable=False, server_default="0.05"),
        sa.Column("base_crit_damage", sa.Numeric(5, 4), nullable=False, server_default="1.5"),
        sa.Column("hp_per_level", sa.Numeric(6, 2), nullable=False),
        sa.Column("attack_per_level", sa.Numeric(6, 2), nullable=False),
        sa.Column("defense_per_level", sa.Numeric(6, 2), nullable=False),
        sa.Column("speed_per_level", sa.Numeric(6, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_character_classes_code", "character_classes", ["code"])

    op.create_table(
        "hero_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("races.id"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("character_classes.id"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_hero_templates_race_id", "hero_templates", ["race_id"])
    op.create_index("ix_hero_templates_class_id", "hero_templates", ["class_id"])

    op.create_table(
        "user_heroes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("hero_template_id", sa.Integer(), sa.ForeignKey("hero_templates.id"), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("xp", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_heroes_user_id", "user_heroes", ["user_id"])
    op.create_index("ix_user_heroes_hero_template_id", "user_heroes", ["hero_template_id"])

    # users.active_hero_id added last: user_heroes must exist first. Nullable
    # FK with ON DELETE SET NULL — deleting a hero (not exposed via any API
    # yet) never leaves users pointing at a dangling row.
    op.add_column("users", sa.Column("active_hero_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_active_hero_id", "users", "user_heroes", ["active_hero_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_active_hero_id", "users", type_="foreignkey")
    op.drop_column("users", "active_hero_id")
    op.drop_table("user_heroes")
    op.drop_table("hero_templates")
    op.drop_table("character_classes")
    op.drop_table("races")
    op.drop_table("users")
