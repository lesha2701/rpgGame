"""Free chest — a thin cooldown gate in front of chest_service.open_chest,
not a parallel implementation. The free chest is an ordinary Chest row
(slug=FREE_CHEST_SLUG, price=0) — open_chest already handles a price=0
chest correctly with no changes needed: debit_coins(0) is a harmless
no-op transaction (same as every reward_service caller that grants xp=0),
and every other step (level gate, loot roll, ChestOpening record, referral
trigger) is the existing chest flow, unmodified.

Cooldown is derived from the most recent ChestOpening for this specific
chest_id — not a new User or Chest column. This is a deliberate step past
the football app's own free_pack_service.py, which stores `User.
free_pack_available_at` directly: RPG already records every opening's
timestamp in ChestOpening, so a second copy of "when did they last open
it" would just be a stale-able cache of information that already exists.
See ARCHITECTURE.md's Stage 10 section for the fuller comparison."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.timeutil import ensure_aware
from app.models.chest import Chest
from app.models.chest_opening import ChestOpening
from app.models.user import User
from app.models.user_hero import UserHero
from app.schemas.chest import ChestOpenResult, FreeChestStatusOut
from app.services.chest_service import chest_to_out, open_chest
from app.services.wallet_service import lock_user_for_update

FREE_CHEST_SLUG = "free-chest"
FREE_CHEST_COOLDOWN = timedelta(hours=24)


async def _get_free_chest_or_404(db: AsyncSession) -> Chest:
    result = await db.execute(select(Chest).where(Chest.slug == FREE_CHEST_SLUG))
    chest = result.unique().scalar_one_or_none()
    if chest is None:
        raise NotFoundError("Free chest is not configured")
    return chest


async def _next_available_at(db: AsyncSession, user_id: int, chest_id: int) -> Optional[datetime]:
    result = await db.execute(
        select(ChestOpening.created_at)
        .where(ChestOpening.user_id == user_id, ChestOpening.chest_id == chest_id)
        .order_by(ChestOpening.created_at.desc())
        .limit(1)
    )
    last_opened_at = result.scalar_one_or_none()
    if last_opened_at is None:
        return None
    return ensure_aware(last_opened_at) + FREE_CHEST_COOLDOWN


async def get_status(db: AsyncSession, user: User) -> FreeChestStatusOut:
    chest = await _get_free_chest_or_404(db)
    next_at = await _next_available_at(db, user.id, chest.id)
    now = datetime.now(timezone.utc)
    is_available = next_at is None or next_at <= now
    return FreeChestStatusOut(
        chest=chest_to_out(chest),
        is_available=is_available,
        next_available_at=None if is_available else next_at.isoformat(),
    )


async def claim(db: AsyncSession, user: User, hero: UserHero) -> ChestOpenResult:
    """Locks the user row itself, BEFORE re-checking the cooldown — not
    just before delegating to open_chest. A naive "check cooldown, then
    call open_chest" wrapper would let two concurrent claims both pass the
    check (neither has opened it yet) and both succeed, since open_chest
    itself has no cooldown concept to re-enforce (paid chests are
    *supposed* to be repeatable, so it has nothing to gate on repetition).
    Locking here first is what actually serializes two concurrent claims:
    the second blocks until the first's entire transaction — including
    open_chest's own commit — finishes, then re-reads the cooldown against
    the now-committed ChestOpening and correctly sees it unavailable.
    open_chest's own internal lock_user_for_update on the same row within
    this same transaction is a harmless re-acquisition, not a second lock
    (Postgres row locks are reentrant within one transaction) — see
    ARCHITECTURE.md's Stage 10 section for the full trace of why a thinner
    wrapper doesn't work."""
    chest = await _get_free_chest_or_404(db)
    locked_user = await lock_user_for_update(db, user.id)

    next_at = await _next_available_at(db, locked_user.id, chest.id)
    now = datetime.now(timezone.utc)
    if next_at is not None and next_at > now:
        raise ConflictError(
            "Free chest is not available yet",
            details={"next_available_at": next_at.isoformat()},
        )

    return await open_chest(db, locked_user, hero, chest.id, idempotency_key=None)
