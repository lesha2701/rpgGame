from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import MinigameAttemptStatus, MinigameType
from app.models.mixins import TimestampMixin


class MinigameAttempt(Base, TimestampMixin):
    """One row per mini-game attempt, shared across every mini-game (a
    `game_type` column, not a table per game) — Memory Sequence and Find
    the Pair both generate a server-side secret at `start` (a random
    sequence / a shuffled pair layout) that has to survive until `submit`/
    `complete` so scoring can check the real answer instead of trusting
    whatever the client echoes back. `payload` is that generated content
    (JSON — same "one blob for the one piece of state that doesn't flatten
    into columns" precedent as ArenaMatch.state/Battle.log). Row starts
    `pending`, becomes `completed` exactly once — a second submit on the
    same id is rejected, not idempotently replayed (matches
    quest_service.claim_quest's "repeat is a genuine 409" precedent, not
    chest_service's idempotency-key replay, since there's no
    Idempotency-Key header on these endpoints for a client to legitimately
    retry with)."""

    __tablename__ = "minigame_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    game_type: Mapped[MinigameType] = mapped_column(SAEnum(MinigameType, name="minigame_type"), nullable=False)
    status: Mapped[MinigameAttemptStatus] = mapped_column(
        SAEnum(MinigameAttemptStatus, name="minigame_attempt_status"),
        nullable=False,
        default=MinigameAttemptStatus.pending,
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    reward_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reward_coins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
