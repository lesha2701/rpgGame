from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("balance >= 0", name="ck_users_balance_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Re-checked against settings.admin_ids on every admin request (not just
    # trusted from this column alone) — see core/dependencies.get_current_admin.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # The one real, spendable game currency (Stage 5) — never confuse with
    # Stage 3's skill-point budget, which is computed from hero.level and
    # has no balance column anywhere. Mutated only via services/wallet_service.py.
    balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # The hero the player currently plays as — same "pick one from what you
    # own" shape as the football app's User.active_badge_id. Nullable: a
    # freshly registered user has no hero yet. Points at user_heroes.id,
    # which is defined after this table (see 0001 migration: the FK is added
    # via a later ALTER TABLE, not here, to avoid a forward table reference).
    # No ORM relationship() on this column on purpose — the hero_service
    # fetches UserHero by id explicitly, which avoids the relationship
    # ambiguity that user_heroes.user_id (a second FK back to this table)
    # would otherwise create, and keeps this the one place we'd otherwise
    # need `foreign_keys=`/`post_update=` bookkeeping.
    active_hero_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_heroes.id", ondelete="SET NULL", use_alter=True, name="fk_users_active_hero_id"),
        nullable=True,
    )

    # Referral link (Stage 10) — set exactly once, at registration
    # (core/dependencies._get_or_create_user), from the raw telegram_id a
    # new user's client sent as X-Referral-Code. Never touched again after
    # that: the "existing user" update path in _get_or_create_user doesn't
    # reference this column at all, so immutability comes from the code
    # structure, not a runtime guard. A self-referencing FK, not a separate
    # Referral table — the relationship data IS this one column; there's
    # nothing else to normalize out of it. referral_count is deliberately
    # NOT a column here — see services/referral_service.py, it's a COUNT
    # over this column, same "derive, don't store" call Stage 8's Quest
    # condition types already made for aggregate numbers.
    referred_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # The one-shot gate for the referrer's reward — NOT a count, NOT
    # inferred from CoinTransaction history. Same role as UserExpedition.
    # claimed_at / UserQuest.claimed_at: a genuine one-time state
    # transition this row's own locked check needs to read back, not
    # something formula-derivable. See services/referral_service.py.
    referral_reward_granted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Mini-game attempt limits (Memory Sequence / Find the Pair) — two
    # independent counters per game, same shape for both so a future third
    # game just adds another 4 columns: `<game>_hourly_attempts` /
    # `<game>_hour_started_at` is a rolling-1h cap on ATTEMPTS (win or
    # lose, still counts — stops someone hammering the endpoint), reset
    # whenever now() has moved past hour_started_at + 1h; `<game>_
    # rewarded_attempts_today` / `<game>_attempts_reset_at` is a rolling-
    # 24h cap on REWARDED attempts only — a player who has hit it can keep
    # playing, they just stop earning xp/coins from it, exactly like every
    # per-game daily cap already documented in this codebase's CLAUDE.md
    # for the football sibling app's own mini-games (same problem, this is
    # RPG's own fresh implementation of it, not shared code). See
    # services/minigame_limits_service.py for the shared check/reset logic
    # both games call through.
    memory_hourly_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    memory_hour_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    memory_rewarded_attempts_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    memory_attempts_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pairs_hourly_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pairs_hour_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pairs_rewarded_attempts_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pairs_attempts_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Same 4-column-per-game shape, for the four mini-games added in a
    # later pass (Training Dummy, Alchemy, Tavern Dice, Three Cups).
    dummy_hourly_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dummy_hour_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dummy_rewarded_attempts_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dummy_attempts_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    alchemy_hourly_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    alchemy_hour_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    alchemy_rewarded_attempts_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    alchemy_attempts_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    dice_hourly_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dice_hour_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dice_rewarded_attempts_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dice_attempts_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cups_hourly_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cups_hour_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cups_rewarded_attempts_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cups_attempts_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
