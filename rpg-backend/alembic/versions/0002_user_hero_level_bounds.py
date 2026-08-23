"""enforce level 1-100 and xp >= 0 on user_heroes at the DB level

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-21

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint("ck_user_heroes_level_range", "user_heroes", "level >= 1 AND level <= 100")
    op.create_check_constraint("ck_user_heroes_xp_non_negative", "user_heroes", "xp >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_user_heroes_xp_non_negative", "user_heroes", type_="check")
    op.drop_constraint("ck_user_heroes_level_range", "user_heroes", type_="check")
