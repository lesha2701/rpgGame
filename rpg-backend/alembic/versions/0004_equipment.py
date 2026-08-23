"""item_templates (catalog), item_affixes (per template), user_items (owned instances, equip state)

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# equipment_slot is reused across TWO tables below (item_templates.slot and
# user_items.slot) — unlike 0003_skills.py's skill_type (used in exactly one
# table, where a plain auto-created Enum was fine), a second create_table()
# using the SAME Enum object tries to CREATE TYPE again and hits the same
# DuplicateObjectError 0003 hit. Passing create_type=False directly on that
# shared object turned out NOT to suppress the automatic per-table creation
# in this SQLAlchemy version either (confirmed live against rpg-postgres —
# the first create_table() call still fails). What actually works: a
# SEPARATE Enum object, sharing the same Postgres type name, with
# create_type=False, used only for the second (and later) table(s) — the
# first table's column keeps the default object that creates it normally.
equipment_slot_enum = sa.Enum(
    "weapon", "helmet", "armor", "boots", "gloves", "ring", "amulet", name="equipment_slot"
)
equipment_slot_enum_existing = sa.Enum(
    "weapon", "helmet", "armor", "boots", "gloves", "ring", "amulet", name="equipment_slot", create_type=False
)
item_rarity_enum = sa.Enum("common", "rare", "epic", "legendary", name="item_rarity")
item_stat_type_enum = sa.Enum("hp", "attack", "defense", "speed", name="item_stat_type")


def upgrade() -> None:
    op.create_table(
        "item_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slot", equipment_slot_enum, nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("rarity", item_rarity_enum, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_item_templates_slot", "item_templates", ["slot"])
    op.create_index("ix_item_templates_tier", "item_templates", ["tier"])
    op.create_index("ix_item_templates_rarity", "item_templates", ["rarity"])
    op.create_check_constraint("ck_item_templates_tier_range", "item_templates", "tier >= 1 AND tier <= 10")

    op.create_table(
        "item_affixes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_template_id", sa.Integer(), sa.ForeignKey("item_templates.id"), nullable=False),
        sa.Column("stat_type", item_stat_type_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_item_affixes_item_template_id", "item_affixes", ["item_template_id"])

    op.create_table(
        "user_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("item_template_id", sa.Integer(), sa.ForeignKey("item_templates.id"), nullable=False),
        # Reuses the equipment_slot enum type already created above (via the
        # create_type=False reference) — denormalized copy of
        # item_templates.slot, see UserItem's docstring.
        sa.Column("slot", equipment_slot_enum_existing, nullable=False),
        sa.Column("equipped_hero_id", sa.Integer(), sa.ForeignKey("user_heroes.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_items_owner_user_id", "user_items", ["owner_user_id"])
    op.create_index("ix_user_items_item_template_id", "user_items", ["item_template_id"])
    op.create_index("ix_user_items_equipped_hero_id", "user_items", ["equipped_hero_id"])
    op.create_index(
        "uq_user_items_one_per_slot_per_hero",
        "user_items",
        ["equipped_hero_id", "slot"],
        unique=True,
        postgresql_where=sa.text("equipped_hero_id IS NOT NULL"),
        sqlite_where=sa.text("equipped_hero_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("user_items")
    op.drop_table("item_affixes")
    op.drop_table("item_templates")
    item_stat_type_enum.drop(op.get_bind(), checkfirst=True)
    item_rarity_enum.drop(op.get_bind(), checkfirst=True)
    equipment_slot_enum.drop(op.get_bind(), checkfirst=True)
