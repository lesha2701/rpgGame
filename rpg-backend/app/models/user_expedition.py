from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ExpeditionStatus

if TYPE_CHECKING:
    from app.models.expedition_template import ExpeditionTemplate


class UserExpedition(Base):
    """One hero's trip through an expedition. Unlike Battle (created already
    resolved), this genuinely spans real time across requests, so it DOES
    need a real in-flight DB state — `status=running` — set at `start()` and
    read back across however many requests happen before `claim()`.

    No `duration_seconds` column here: `completed_at` is instead computed
    ONCE at start time (`started_at + template.duration_seconds`)
    and stored, rather than re-read from the template on every check. Two
    reasons, not just caching: (1) it freezes the deadline a player already
    committed to — a later admin rebalance of the template's duration must
    not retroactively shift an expedition already in flight, matching
    ChestOpening.price_paid's "snapshot economic terms at commit time"
    precedent; (2) `reward_xp`/`reward_coins` are snapshotted the same way,
    for the same reason, and checking completion is then a pure comparison
    against this row alone — no join to the (possibly since-edited)
    template needed to answer "is this done yet".

    No background job ever touches `status` or `completed_at` — see
    ExpeditionStatus's docstring and expedition_service.py for how
    "completed" is computed at read time instead of stored."""

    __tablename__ = "user_expeditions"
    __table_args__ = (
        CheckConstraint("reward_xp >= 0", name="ck_user_expeditions_reward_xp_non_negative"),
        CheckConstraint("reward_coins >= 0", name="ck_user_expeditions_reward_coins_non_negative"),
        # At most one RUNNING expedition per hero, enforced at the DB level
        # regardless of which code path inserts a row — defense in depth
        # behind the primary correctness mechanism, which is locking the
        # hero row in expedition_service.start_expedition before checking
        # for an existing one (same "lock first, then check-then-act"
        # pattern as Stage 4's one-equipped-item-per-slot partial index).
        Index(
            "uq_user_expeditions_one_running_per_hero",
            "hero_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
            sqlite_where=text("status = 'running'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    hero_id: Mapped[int] = mapped_column(ForeignKey("user_heroes.id"), nullable=False, index=True)
    expedition_template_id: Mapped[int] = mapped_column(
        ForeignKey("expedition_templates.id"), nullable=False, index=True
    )

    status: Mapped[ExpeditionStatus] = mapped_column(
        SAEnum(ExpeditionStatus, name="expedition_status"), nullable=False
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reward_xp: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_coins: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    expedition_template: Mapped["ExpeditionTemplate"] = relationship("ExpeditionTemplate", lazy="joined")
