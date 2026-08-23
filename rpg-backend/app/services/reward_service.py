"""The one place that grants "XP + coins" as a single atomic hero reward.

Before this existed, battle_service.start_battle and expedition_service.
claim_expedition each independently implemented the same three-step
sequence (lock the user row, grant_xp, credit_coins) with only the
TransactionType/description/related_object differing — see ARCHITECTURE.md's
Stage 8 section. Quest claims needed the same sequence a third time, which
is what made extracting it worthwhile: one place to get the lock order
right, not three.

Does not invent any new formula — it only composes hero_service.grant_xp
and wallet_service.credit_coins, unchanged. Does not commit (or rollback):
transactionally composable by the same contract those two functions already
follow, so a caller can fold this together with its own row mutations
(a Battle insert, UserExpedition.claimed_at, UserQuest.claimed_at) into one
commit — the reward must never land if the caller's own record doesn't."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TransactionType
from app.models.user import User
from app.models.user_hero import UserHero
from app.services.hero_service import grant_xp
from app.services.wallet_service import credit_coins, lock_user_for_update


async def grant_hero_reward(
    db: AsyncSession,
    hero_id: int,
    user_id: int,
    xp: int,
    coins: int,
    tx_type: TransactionType,
    description: str = "",
    related_object_type: Optional[str] = None,
    related_object_id: Optional[int] = None,
) -> tuple[UserHero, User]:
    """Locks the user row, grants xp to the hero, credits coins to the user
    — same lock order every existing caller already used by convention
    (user, then hero via grant_xp's own internal lock_hero_for_update),
    now enforced by there being exactly one function that does it. coins is
    still credited even when 0 (matches every pre-existing caller's
    behavior — this does not introduce a new "skip the zero-amount
    transaction" branch that would change what gets recorded)."""
    locked_user = await lock_user_for_update(db, user_id)
    locked_hero, _level_result = await grant_xp(db, hero_id, xp)
    await credit_coins(db, locked_user, coins, tx_type, description, related_object_type, related_object_id)
    return locked_hero, locked_user
