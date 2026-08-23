from sqlalchemy import Boolean, CheckConstraint, Enum as SAEnum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import QuestConditionType
from app.models.mixins import TimestampMixin


class QuestDefinition(Base, TimestampMixin):
    """Catalog of quests — same authored-stat-block shape as EnemyTemplate/
    ExpeditionTemplate: no formula, numbers are hand-set and admin-tunable.
    A quest's progress is never stored anywhere (see UserQuest's docstring)
    — condition_type + target_value fully describe what to check, and
    services/quest_progression.py computes the current value by querying
    whichever existing table that condition_type is about."""

    __tablename__ = "quest_definitions"
    __table_args__ = (
        CheckConstraint("target_value > 0", name="ck_quest_definitions_target_value_positive"),
        CheckConstraint("reward_xp >= 0", name="ck_quest_definitions_reward_xp_non_negative"),
        CheckConstraint("reward_coins >= 0", name="ck_quest_definitions_reward_coins_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    condition_type: Mapped[QuestConditionType] = mapped_column(
        SAEnum(QuestConditionType, name="quest_condition_type"), nullable=False
    )
    target_value: Mapped[int] = mapped_column(Integer, nullable=False)

    reward_xp: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_coins: Mapped[int] = mapped_column(Integer, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
