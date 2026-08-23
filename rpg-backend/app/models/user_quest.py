from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.quest_definition import QuestDefinition


class UserQuest(Base):
    """One user's instance of one QuestDefinition. This row is purely
    "has this user claimed this quest yet" — deliberately NOT "how far
    along is this user on this quest": there is no `progress` column here
    on purpose. Progress is always computed live by querying Battle/
    ArenaMatch/UserExpedition/ChestOpening/UserHero/UserItem/
    CharacterSkill/UserCampaignNodeClear directly
    (services/quest_progression.py) — the same "derive, don't store" call
    this project has made everywhere else (hero stats, XP-to-next-level,
    item power, expedition "completed"). Storing progress here would mean
    either those other services having to know quests exist and push
    updates into this table (an event-bus this project explicitly must
    not build), or a background job re-scanning everything — both are
    exactly what this design avoids.

    `slot_index` (0..ACTIVE_QUEST_SLOT_COUNT-1, NULL = not currently
    active) is the one rotation-tracking field, added for the 5-active-
    slots mechanic (see quest_service.py) — deliberately still no
    metric-baseline column like the football app's UserTask: each
    QuestDefinition is assigned to a given user AT MOST ONCE ever (a row
    existing here, regardless of slot_index, permanently excludes that
    definition from being redrawn for this user — see
    quest_service._ensure_slots_filled). A baseline would only be needed
    for a REPEATABLE assignment, which this deliberately isn't: RPG's
    condition types are live lifetime counts with no baseline concept
    anywhere else, and reassigning the same definition later would let an
    already-exceeded lifetime count instantly "complete" it again — the
    same trap the football app's metric_baseline exists to avoid. Kept
    simple by sidestepping the problem instead of solving it: the
    ever-growing QuestDefinition catalog (see seed.py's QUESTS) is the
    pool a user's 5 slots draw from, once each, forever."""

    __tablename__ = "user_quests"
    __table_args__ = (
        UniqueConstraint("user_id", "quest_definition_id", name="uq_user_quest"),
        Index(
            "uq_user_quest_slot",
            "user_id",
            "slot_index",
            unique=True,
            postgresql_where=text("slot_index IS NOT NULL"),
            sqlite_where=text("slot_index IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    quest_definition_id: Mapped[int] = mapped_column(ForeignKey("quest_definitions.id"), nullable=False, index=True)

    slot_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    quest_definition: Mapped["QuestDefinition"] = relationship("QuestDefinition", lazy="joined")
