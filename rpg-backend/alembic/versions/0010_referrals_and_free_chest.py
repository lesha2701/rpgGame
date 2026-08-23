"""referrals (User.referred_by_id / referral_reward_granted — no separate
Referral table, no new columns for the free chest, see ARCHITECTURE.md's
Stage 10 section)

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # transaction_type already exists (created in 0005) — adding a new
    # member needs its own ALTER TYPE; op.add_column()/op.create_table()
    # never extend an existing enum type on their own. Applied proactively
    # (fourth time now) — see ARCHITECTURE.md's Stage 6 section for the
    # underlying gotcha.
    op.execute("ALTER TYPE transaction_type ADD VALUE IF NOT EXISTS 'referral_reward'")

    op.add_column("users", sa.Column("referred_by_id", sa.Integer(), nullable=True))
    op.add_column(
        "users",
        sa.Column("referral_reward_granted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_users_referred_by_id", "users", ["referred_by_id"])
    op.create_foreign_key(
        "fk_users_referred_by_id", "users", "users", ["referred_by_id"], ["id"], ondelete="SET NULL"
    )

    # No new table for the free chest — it's an ordinary Chest row (see
    # app/seed.py's free-chest entry) and its cooldown is derived from
    # ChestOpening.created_at, not a new column anywhere.


def downgrade() -> None:
    op.drop_constraint("fk_users_referred_by_id", "users", type_="foreignkey")
    op.drop_index("ix_users_referred_by_id", table_name="users")
    op.drop_column("users", "referral_reward_granted")
    op.drop_column("users", "referred_by_id")
    # No ALTER TYPE ... DROP VALUE in Postgres — same limitation documented
    # on every prior stage's downgrade(). "referral_reward" stays in
    # transaction_type's set of possible values even after this downgrade.
