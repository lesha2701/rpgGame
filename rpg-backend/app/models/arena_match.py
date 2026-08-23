from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, JSON, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import ArenaMatchStatus


class ArenaMatch(Base):
    """One PvP match — mutable while `status=running`, then frozen forever
    once `status=finished` (nothing ever writes to a finished row again).
    Structurally closer to UserExpedition (spans real time across requests,
    mutates in place, then freezes) than to Battle (created already
    resolved in one insert) — a single table serves as both the live match
    state AND its own history record, exactly like UserExpedition's
    `list_history` just queries UserExpedition regardless of status. No
    separate ArenaMatchResult table.

    `state` (JSON) holds the one piece of state that genuinely can't be
    flattened into columns without an unreasonable number of them: each
    side's `battle_engine.CombatantState` (HP/cooldowns/buffs/shield/dot/
    stun) plus their frozen combat-input snapshot (stats + skills, copied
    from hero_service/battle_service ONCE at match creation — see
    arena_service.create_match) plus whichever side's pending action for
    the CURRENT round hasn't resolved yet. Same precedent as `Battle.log`
    already being JSON in this codebase, not a football import.

    No `player_a_last_acted_round`/`player_b_last_acted_round` columns:
    idempotency for a repeated action submission is derived entirely from
    comparing the client-supplied `round` against `current_round`, plus
    checking whether `state[side]["pending_action"]` is already set — see
    arena_service.submit_action's docstring for why that's sufficient
    (including the "retry arrives after the round already resolved" case)
    without extra columns duplicating information `state` already has.

    No relationships (hero/user) are declared here on purpose — every
    prior `lazy="joined"` FOR UPDATE gotcha in this codebase (documented in
    ARCHITECTURE.md) came from an eagerly-loaded relationship colliding
    with an outer join; this table just doesn't have one, so a plain
    `.with_for_update()` is always safe here, no `of=` scoping needed."""

    __tablename__ = "arena_matches"
    __table_args__ = (
        CheckConstraint("player_a_hero_id != player_b_hero_id", name="ck_arena_matches_distinct_heroes"),
        CheckConstraint("current_round >= 1", name="ck_arena_matches_round_positive"),
        CheckConstraint("reward_xp >= 0", name="ck_arena_matches_reward_xp_non_negative"),
        CheckConstraint("reward_coins >= 0", name="ck_arena_matches_reward_coins_non_negative"),
        # Defense in depth, not the primary correctness mechanism (that's
        # locking both hero rows, sorted by id, before the "does either
        # hero already have a running match" check in
        # arena_service.create_match — same pattern Stage 7 used for one
        # hero/one expedition, extended to two heroes locked together).
        # Two separate partial indexes can't express "unique across the
        # union of both hero columns" — a hero could in principle still be
        # player_a in one running match and player_b in another if
        # something bypassed the service-layer lock entirely. Documented
        # honestly rather than oversold.
        Index(
            "uq_arena_matches_player_a_running",
            "player_a_hero_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
            sqlite_where=text("status = 'running'"),
        ),
        Index(
            "uq_arena_matches_player_b_running",
            "player_b_hero_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
            sqlite_where=text("status = 'running'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    player_a_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    player_a_hero_id: Mapped[int] = mapped_column(ForeignKey("user_heroes.id"), nullable=False, index=True)
    player_b_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    player_b_hero_id: Mapped[int] = mapped_column(ForeignKey("user_heroes.id"), nullable=False, index=True)

    status: Mapped[ArenaMatchStatus] = mapped_column(
        SAEnum(ArenaMatchStatus, name="arena_match_status"), nullable=False
    )
    current_round: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # {"turn": int, "player_a": {...CombatantState fields..., "skills": [...]},
    #  "player_b": {...}} — see arena_service.py for the exact shape built/read.
    state: Mapped[dict] = mapped_column(JSON, nullable=False)
    log: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    round_deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # index=True added in Stage 11 (0011_leaderboard_indexes) — the
    # arena_wins leaderboard GROUP BYs this column directly.
    winner_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    reward_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reward_coins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
