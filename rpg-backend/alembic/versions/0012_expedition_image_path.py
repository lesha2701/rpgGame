"""Adds ExpeditionTemplate.image_path — every other authored-catalog model
(Race, CharacterClass, HeroTemplate, EnemyTemplate, ItemTemplate, Chest)
already had this column since its own migration; expeditions were the one
holdout. Needed now for admin image upload (locations for expeditions).

Revision ID: 0012
Revises: 0011
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("expedition_templates", sa.Column("image_path", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("expedition_templates", "image_path")
