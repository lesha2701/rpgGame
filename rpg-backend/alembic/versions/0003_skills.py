"""skill_definitions (per class) and character_skills (per hero progress)

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

skill_type_enum = sa.Enum(
    "damage", "heal", "buff", "debuff", "dot", "shield", "stun", name="skill_type"
)


def upgrade() -> None:
    # No separate skill_type_enum.create() call here: sa.Enum's Postgres
    # dialect already emits its own checkfirst-safe CREATE TYPE as part of
    # create_table() below when the column is first defined — calling
    # .create() first *and* letting create_table's column processing create
    # it again produces two competing CREATE TYPE statements (the second
    # isn't checkfirst-guarded the same way), which fails with
    # DuplicateObjectError. Pick one; create_table's own handling is enough.
    op.create_table(
        "skill_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("character_classes.id"), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("skill_type", skill_type_enum, nullable=False),
        sa.Column("base_power", sa.Numeric(8, 2), nullable=False),
        sa.Column("power_per_skill_level", sa.Numeric(8, 2), nullable=False),
        sa.Column("cooldown_turns", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required_hero_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_skill_definitions_class_id", "skill_definitions", ["class_id"])
    op.create_unique_constraint("uq_skill_definitions_class_code", "skill_definitions", ["class_id", "code"])
    op.create_check_constraint(
        "ck_skill_definitions_required_level_range",
        "skill_definitions",
        "required_hero_level >= 1 AND required_hero_level <= 100",
    )

    op.create_table(
        "character_skills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hero_id", sa.Integer(), sa.ForeignKey("user_heroes.id"), nullable=False),
        sa.Column("skill_definition_id", sa.Integer(), sa.ForeignKey("skill_definitions.id"), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_character_skills_hero_id", "character_skills", ["hero_id"])
    op.create_index("ix_character_skills_skill_definition_id", "character_skills", ["skill_definition_id"])
    op.create_unique_constraint(
        "uq_character_skills_hero_skill", "character_skills", ["hero_id", "skill_definition_id"]
    )
    op.create_check_constraint("ck_character_skills_level_range", "character_skills", "level >= 1 AND level <= 10")


def downgrade() -> None:
    op.drop_table("character_skills")
    op.drop_table("skill_definitions")
    skill_type_enum.drop(op.get_bind(), checkfirst=True)
