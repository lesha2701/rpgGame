"""coins (users.balance, users.is_admin, coin_transactions) and chests (chests, chest_rarity_probabilities, chest_openings)

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# transaction_type is brand new and used exactly once (coin_transactions.type)
# — a plain auto-creating Enum works fine here, matching 0003_skills.py's
# single-use skill_type.
transaction_type_enum = sa.Enum("chest_purchase", "admin_grant", name="transaction_type")

# item_rarity, by contrast, already exists — created by 0004_equipment.py for
# item_templates.rarity, in a *separate, already-committed* migration.
# Empirically verified against a real Postgres instance: Alembic's
# op.create_table() unconditionally attempts CREATE TYPE for every Enum-typed
# column it processes and ignores create_type=False entirely (that flag only
# suppresses creation via SQLAlchemy's own Base.metadata.create_all(), a
# different code path — confirmed by direct source inspection of
# sqlalchemy.dialects.postgresql.named_types.NamedType._on_table_create,
# and by reproducing the failure with a minimal op.create_table() call in
# isolation). 0004's *own* create_type=False workaround only happened to work
# because reusing a type across two tables *within the same migration*
# benefits from an internal ddl-runner memo that isn't shared across
# separate migration files — it doesn't generalize to "reference a type an
# earlier, already-applied migration created". The only reliable fix for
# that case: add the enum-typed columns via raw ALTER TABLE, bypassing
# SQLAlchemy's Enum-DDL machinery entirely for just these two columns.


def upgrade() -> None:
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("balance", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint("ck_users_balance_non_negative", "users", "balance >= 0")

    op.create_table(
        "coin_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_before", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("type", transaction_type_enum, nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("related_object_type", sa.String(length=32), nullable=True),
        sa.Column("related_object_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_coin_transactions_user_id", "coin_transactions", ["user_id"])

    op.create_table(
        "chests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("image_path", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Raw SQL — see the module docstring above for why this column can't be
    # declared inline via sa.Column(..., sa.Enum(..., name="item_rarity")).
    op.execute("ALTER TABLE chests ADD COLUMN guaranteed_min_rarity item_rarity")
    op.create_unique_constraint("uq_chests_slug", "chests", ["slug"])
    op.create_index("ix_chests_tier", "chests", ["tier"])
    op.create_check_constraint("ck_chests_tier_range", "chests", "tier >= 1 AND tier <= 10")

    op.create_table(
        "chest_rarity_probabilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chest_id", sa.Integer(), sa.ForeignKey("chests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("probability", sa.Numeric(6, 4), nullable=False),
    )
    # Table is empty at creation time, so NOT NULL with no default is safe.
    op.execute("ALTER TABLE chest_rarity_probabilities ADD COLUMN rarity item_rarity NOT NULL")
    op.create_index("ix_chest_rarity_probabilities_chest_id", "chest_rarity_probabilities", ["chest_id"])
    op.create_unique_constraint("uq_chest_rarity", "chest_rarity_probabilities", ["chest_id", "rarity"])

    op.create_table(
        "chest_openings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chest_id", sa.Integer(), sa.ForeignKey("chests.id"), nullable=False),
        sa.Column("reward_user_item_id", sa.Integer(), sa.ForeignKey("user_items.id"), nullable=False),
        sa.Column("price_paid", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chest_openings_user_id", "chest_openings", ["user_id"])
    op.create_index("ix_chest_openings_chest_id", "chest_openings", ["chest_id"])
    op.create_index("ix_chest_openings_idempotency_key", "chest_openings", ["idempotency_key"])
    op.create_unique_constraint("uq_chest_opening_idem", "chest_openings", ["user_id", "idempotency_key"])


def downgrade() -> None:
    op.drop_table("chest_openings")
    op.drop_table("chest_rarity_probabilities")
    op.drop_table("chests")
    op.drop_table("coin_transactions")
    op.drop_constraint("ck_users_balance_non_negative", "users", type_="check")
    op.drop_column("users", "balance")
    op.drop_column("users", "is_admin")
    transaction_type_enum.drop(op.get_bind(), checkfirst=True)
    # item_rarity is NOT dropped here — it's owned by 0004_equipment.py
    # (item_templates.rarity still uses it after this migration downgrades).
