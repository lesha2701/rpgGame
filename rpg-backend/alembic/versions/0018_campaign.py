"""Stage 13 — PvE Campaign & Interactive Combat 2.0. Purely additive: new
tables (campaign_regions/campaign_nodes/campaign_node_edges/
user_campaign_node_clears/enemy_abilities/enemy_resistances/boss_phases/
item_effects/campaign_battles) plus new columns on enemy_templates
(is_boss/stun_immune/behavior_pattern) and skill_definitions
(buff_stat/is_interrupt), all with defaults that reproduce prior behavior
exactly (see EnemyTemplate/SkillDefinition/battle_engine.py docstrings).
Existing tables (battles, arena_matches, ...) are untouched.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

campaign_battle_status_enum = sa.Enum("running", "finished", name="campaign_battle_status")
campaign_node_type_enum = sa.Enum(
    "battle", "elite", "boss", "story_event", "treasure", "merchant", "rest", name="campaign_node_type"
)
item_effect_trigger_enum = sa.Enum(
    "on_crit", "on_defend", "on_hit_dealt", "on_hit_taken", "on_status_applied", "passive",
    name="item_effect_trigger",
)
item_effect_type_enum = sa.Enum(
    "apply_status", "damage_bonus_vs_status", "shield_bonus_pct", "lifesteal_pct", name="item_effect_type"
)
# battle_result/skill_type already exist (created in 0006/0003) — reused
# as-is (create_type=False, the dialect-specific PGEnum honors this on
# create_table where a plain sa.Enum silently ignores it), not recreated.
battle_result_enum = PGEnum("won", "lost", name="battle_result", create_type=False)
skill_type_enum = PGEnum(
    "damage", "heal", "buff", "debuff", "dot", "shield", "stun", name="skill_type", create_type=False
)


def upgrade() -> None:
    op.execute("ALTER TYPE transaction_type ADD VALUE IF NOT EXISTS 'campaign_reward'")

    # --- enemy_templates additions ---
    op.add_column("enemy_templates", sa.Column("is_boss", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("enemy_templates", sa.Column("stun_immune", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("enemy_templates", sa.Column("behavior_pattern", sa.JSON(), nullable=True))

    # --- skill_definitions additions ---
    op.add_column(
        "skill_definitions", sa.Column("buff_stat", sa.String(16), nullable=False, server_default="attack")
    )
    op.add_column(
        "skill_definitions", sa.Column("is_interrupt", sa.Boolean(), nullable=False, server_default="false")
    )

    # --- enemy_abilities ---
    op.create_table(
        "enemy_abilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enemy_template_id", sa.Integer(), sa.ForeignKey("enemy_templates.id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("skill_type", skill_type_enum, nullable=False),
        sa.Column("power", sa.Numeric(8, 2), nullable=False),
        sa.Column("cooldown_turns", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("buff_stat", sa.String(16), nullable=False, server_default="attack"),
        sa.Column("status_label", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("enemy_template_id", "code", name="uq_enemy_abilities_template_code"),
    )
    op.create_index("ix_enemy_abilities_enemy_template_id", "enemy_abilities", ["enemy_template_id"])

    # --- enemy_resistances ---
    op.create_table(
        "enemy_resistances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enemy_template_id", sa.Integer(), sa.ForeignKey("enemy_templates.id"), nullable=False),
        sa.Column("status_label", sa.String(32), nullable=False),
        sa.Column("multiplier", sa.Numeric(5, 2), nullable=False, server_default="1.0"),
        sa.UniqueConstraint("enemy_template_id", "status_label", name="uq_enemy_resistances_template_label"),
    )
    op.create_index("ix_enemy_resistances_enemy_template_id", "enemy_resistances", ["enemy_template_id"])

    # --- boss_phases ---
    op.create_table(
        "boss_phases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enemy_template_id", sa.Integer(), sa.ForeignKey("enemy_templates.id"), nullable=False),
        sa.Column("phase_order", sa.Integer(), nullable=False),
        sa.Column("hp_threshold_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("behavior_pattern", sa.JSON(), nullable=True),
        sa.Column("attack_multiplier", sa.Numeric(5, 2), nullable=False, server_default="1.0"),
        sa.Column("defense_multiplier", sa.Numeric(5, 2), nullable=False, server_default="1.0"),
        sa.Column("unlock_ability_code", sa.String(64), nullable=True),
        sa.Column("transition_text", sa.Text(), nullable=True),
        sa.UniqueConstraint("enemy_template_id", "phase_order", name="uq_boss_phases_template_order"),
        sa.CheckConstraint("hp_threshold_pct >= 0 AND hp_threshold_pct <= 100", name="ck_boss_phases_threshold_range"),
    )
    op.create_index("ix_boss_phases_enemy_template_id", "boss_phases", ["enemy_template_id"])

    # --- item_effects ---
    op.create_table(
        "item_effects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_template_id", sa.Integer(), sa.ForeignKey("item_templates.id"), nullable=False),
        sa.Column("trigger", item_effect_trigger_enum, nullable=False),
        sa.Column("effect_type", item_effect_type_enum, nullable=False),
        sa.Column("status_label", sa.String(32), nullable=True),
        sa.Column("magnitude", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("duration_turns", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_item_effects_item_template_id", "item_effects", ["item_template_id"])

    # --- campaign_regions ---
    op.create_table(
        "campaign_regions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_path", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- campaign_nodes ---
    op.create_table(
        "campaign_nodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("campaign_regions.id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("node_type", campaign_node_type_enum, nullable=False),
        sa.Column("enemy_template_id", sa.Integer(), sa.ForeignKey("enemy_templates.id"), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_campaign_nodes_region_id", "campaign_nodes", ["region_id"])
    op.create_index("ix_campaign_nodes_enemy_template_id", "campaign_nodes", ["enemy_template_id"])

    # --- campaign_node_edges ---
    op.create_table(
        "campaign_node_edges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("from_node_id", sa.Integer(), sa.ForeignKey("campaign_nodes.id"), nullable=False),
        sa.Column("to_node_id", sa.Integer(), sa.ForeignKey("campaign_nodes.id"), nullable=False),
        sa.UniqueConstraint("from_node_id", "to_node_id", name="uq_campaign_node_edges_pair"),
        sa.CheckConstraint("from_node_id != to_node_id", name="ck_campaign_node_edges_no_self_loop"),
    )
    op.create_index("ix_campaign_node_edges_from_node_id", "campaign_node_edges", ["from_node_id"])
    op.create_index("ix_campaign_node_edges_to_node_id", "campaign_node_edges", ["to_node_id"])

    # --- user_campaign_node_clears ---
    op.create_table(
        "user_campaign_node_clears",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("node_id", sa.Integer(), sa.ForeignKey("campaign_nodes.id"), nullable=False),
        sa.Column("first_cleared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_cleared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clear_count", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("user_id", "node_id", name="uq_user_campaign_node_clears_user_node"),
    )
    op.create_index("ix_user_campaign_node_clears_user_id", "user_campaign_node_clears", ["user_id"])
    op.create_index("ix_user_campaign_node_clears_node_id", "user_campaign_node_clears", ["node_id"])

    # --- campaign_battles ---
    op.create_table(
        "campaign_battles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("hero_id", sa.Integer(), sa.ForeignKey("user_heroes.id"), nullable=False),
        sa.Column("node_id", sa.Integer(), sa.ForeignKey("campaign_nodes.id"), nullable=False),
        sa.Column("enemy_template_id", sa.Integer(), sa.ForeignKey("enemy_templates.id"), nullable=False),
        sa.Column("status", campaign_battle_status_enum, nullable=False),
        sa.Column("current_round", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("log", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("result", battle_result_enum, nullable=True),
        sa.Column("is_first_clear", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reward_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reward_coins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("current_round >= 1", name="ck_campaign_battles_round_positive"),
        sa.CheckConstraint("reward_xp >= 0", name="ck_campaign_battles_reward_xp_non_negative"),
        sa.CheckConstraint("reward_coins >= 0", name="ck_campaign_battles_reward_coins_non_negative"),
    )
    op.create_index("ix_campaign_battles_user_id", "campaign_battles", ["user_id"])
    op.create_index("ix_campaign_battles_hero_id", "campaign_battles", ["hero_id"])
    op.create_index("ix_campaign_battles_node_id", "campaign_battles", ["node_id"])
    op.create_index("ix_campaign_battles_enemy_template_id", "campaign_battles", ["enemy_template_id"])
    op.create_index(
        "uq_campaign_battles_hero_running",
        "campaign_battles",
        ["hero_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
        sqlite_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_table("campaign_battles")
    op.drop_table("user_campaign_node_clears")
    op.drop_table("campaign_node_edges")
    op.drop_table("campaign_nodes")
    op.drop_table("campaign_regions")
    op.drop_table("item_effects")
    op.drop_table("boss_phases")
    op.drop_table("enemy_resistances")
    op.drop_table("enemy_abilities")

    op.drop_column("skill_definitions", "is_interrupt")
    op.drop_column("skill_definitions", "buff_stat")

    op.drop_column("enemy_templates", "behavior_pattern")
    op.drop_column("enemy_templates", "stun_immune")
    op.drop_column("enemy_templates", "is_boss")

    campaign_battle_status_enum.drop(op.get_bind(), checkfirst=True)
    campaign_node_type_enum.drop(op.get_bind(), checkfirst=True)
    item_effect_trigger_enum.drop(op.get_bind(), checkfirst=True)
    item_effect_type_enum.drop(op.get_bind(), checkfirst=True)
    # No ALTER TYPE ... DROP VALUE in Postgres — "campaign_reward" stays in
    # transaction_type's set of possible values even after this downgrade,
    # same documented limitation as every earlier migration that added one.
