from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import BattleResult

if TYPE_CHECKING:
    from app.models.enemy_template import EnemyTemplate


class Battle(Base):
    """An immutable record of one already-resolved PvE fight — NOT a
    resumable session. There is no RUNNING state and never a second
    "complete" step to call: start_battle() simulates the whole fight
    in-memory (battle_engine.simulate_battle, pure) and this row is created
    once, already carrying its final result. That structurally rules out
    "complete the same battle twice" — there's no separate completion step
    to repeat. The only remaining risk is a client retrying the exact same
    POST /battles request, handled by the same idempotency-key + unique-
    constraint + commit-time IntegrityError pattern as ChestOpening.

    `log` is the full turn-by-turn output of the simulation (see
    battle_engine.TurnLogEntry) — stored so GET /battles/{id} can show
    exactly what happened, and so a future frontend has everything it needs
    to animate the fight without re-simulating anything."""

    __tablename__ = "battles"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_battle_idem"),
        CheckConstraint("turns >= 0", name="ck_battles_turns_non_negative"),
        CheckConstraint("reward_xp >= 0", name="ck_battles_reward_xp_non_negative"),
        CheckConstraint("reward_coins >= 0", name="ck_battles_reward_coins_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    hero_id: Mapped[int] = mapped_column(ForeignKey("user_heroes.id"), nullable=False, index=True)
    enemy_template_id: Mapped[int] = mapped_column(ForeignKey("enemy_templates.id"), nullable=False, index=True)

    result: Mapped[BattleResult] = mapped_column(SAEnum(BattleResult, name="battle_result"), nullable=False)
    turns: Mapped[int] = mapped_column(Integer, nullable=False)
    log: Mapped[list] = mapped_column(JSON, nullable=False)

    reward_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reward_coins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    enemy_template: Mapped["EnemyTemplate"] = relationship("EnemyTemplate", lazy="joined")
