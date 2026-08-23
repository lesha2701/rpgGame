"""Adds 'admin_deduct' to the transaction_type enum — mirrors 'admin_grant'
for the new admin coin-deduction endpoint. Same ALTER TYPE ADD VALUE gotcha
as 0007/0006: op.create_table() only handles first-creation of a Postgres
enum, adding a member to an existing one needs its own statement.

Revision ID: 0013
Revises: 0012
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE transaction_type ADD VALUE IF NOT EXISTS 'admin_deduct'")


def downgrade() -> None:
    # No ALTER TYPE ... DROP VALUE in Postgres — same limitation documented
    # on 0006/0007's downgrades. "admin_deduct" stays in transaction_type's
    # set of possible values even after this downgrade.
    pass
