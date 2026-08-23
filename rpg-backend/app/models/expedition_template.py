from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class ExpeditionTemplate(Base, TimestampMixin):
    """Catalog of expeditions a hero can be sent on — an authored stat
    block (duration/level-gate/reward), same shape as EnemyTemplate: no
    tier-formula derivation, numbers are hand-set and admin-tunable.
    `UserExpedition` snapshots this row's duration_seconds/reward_xp/
    reward_coins at start time (see that model's docstring) — a later
    rebalance of this template never affects an expedition already
    in flight."""

    __tablename__ = "expedition_templates"
    __table_args__ = (
        CheckConstraint("duration_seconds > 0", name="ck_expedition_templates_duration_positive"),
        CheckConstraint("required_hero_level >= 1", name="ck_expedition_templates_level_positive"),
        CheckConstraint("reward_xp >= 0", name="ck_expedition_templates_reward_xp_non_negative"),
        CheckConstraint("reward_coins >= 0", name="ck_expedition_templates_reward_coins_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Location artwork (0012) — the one authored-catalog model that didn't
    # already have this column; every sibling (Race/CharacterClass/
    # HeroTemplate/EnemyTemplate/ItemTemplate/Chest) has had it since its
    # own migration.
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    required_hero_level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    reward_xp: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_coins: Mapped[int] = mapped_column(Integer, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
