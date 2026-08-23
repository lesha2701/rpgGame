"""Per-instance hero name (UserHero.name), nullable — existing rows fall
back to their HeroTemplate.name at read time (see hero_service.hero_to_out),
so no backfill is needed. New heroes always get one going forward: creation
now requires a name (schemas.character.CreateHeroRequest.name).

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_heroes", sa.Column("name", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("user_heroes", "name")
