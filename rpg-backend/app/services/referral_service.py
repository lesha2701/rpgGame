"""Referral rewards. The connection (User.referred_by_id) is captured once,
at registration (core/dependencies._get_or_create_user), entirely separately
from the reward — which fires on the referred user's first genuine
engagement action: the first chest they open, paid or free (see
chest_service.open_chest, the single call site).

Ported in spirit, not in code, from the football app's pack_service.
_credit_referral_bonus / maybe_grant_referral_bonus_for_locked_user: same
anti-farm reasoning ("crediting it immediately on registration would let
anyone farm referral rewards with disposable, never-played accounts via
this client-supplied header alone" — see core/dependencies.py), same
one-shot referral_reward_granted gate rather than a count/paid-purchase
check, same "lock the referrer after the caller's already-locked user"
shape. Not copied verbatim: RPG's single open_chest call site replaces
football's three separate ones (open_pack/claim_free_pack/
grant_bonus_pack_opening), referral_count is derived here (COUNT), never a
stored/incremented column the way football's is, and the reward flows
through reward_service.grant_hero_reward instead of two bare credit_coins
calls, since RPG's reward vocabulary includes XP where football's doesn't."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TransactionType
from app.models.user import User
from app.services.hero_service import get_active_hero
from app.services.reward_service import grant_hero_reward
from app.services.wallet_service import lock_user_for_update

# Illustrative V1 balance, not final tuning — same caveat as every other
# seeded/constant reward in this codebase. Coins only (xp=0): football's own
# referral bonus is coins-only too (it has no hero/xp concept at all); there
# is no per-template catalog row a referral reward could naturally live on
# (unlike Enemy/Expedition/Quest), so this follows Arena's precedent
# (Stage 9) of a plain module constant rather than inventing a config row.
REFERRAL_REWARD_XP = 0
REFERRAL_REWARD_COINS = 25


async def referral_count(db: AsyncSession, user_id: int) -> int:
    """Successful (reward-granted) referrals — derived via COUNT, never
    stored. Same "compute from existing rows, don't maintain a counter
    column" call Stage 8's Quest condition types already made."""
    result = await db.execute(
        select(func.count(User.id)).where(User.referred_by_id == user_id, User.referral_reward_granted.is_(True))
    )
    return result.scalar_one()


async def total_referred_count(db: AsyncSession, user_id: int) -> int:
    """Everyone who registered with this user's code, regardless of
    whether the reward has fired yet — Stage 11's Profile statistics wants
    both this raw number and `referral_count`'s "successful" one side by
    side, so a visitor can tell "invited" apart from "converted". Not a
    stored counter either — same derive-from-existing-rows shape."""
    result = await db.execute(select(func.count(User.id)).where(User.referred_by_id == user_id))
    return result.scalar_one()


async def maybe_grant_referral_reward(db: AsyncSession, referred_user: User) -> None:
    """Call after a chest opening succeeds (chest_service.open_chest, the
    only call site), before commit, with `referred_user` already locked by
    the caller. No-op, silently, unless there's an unrewarded referrer link
    — and even then, no-ops if the referrer has no active hero yet:
    reward_service.grant_hero_reward needs a real hero_id (grant_xp locks
    the hero row even for xp=0), and a chest opening must never fail
    because of the REFERRER's account state. This edge case is deliberately
    left unresolved rather than special-cased — see ARCHITECTURE.md's
    Stage 10 section — the reward is simply never granted in that case,
    not deferred or retried.

    Locks the referrer *after* `referred_user` (already locked by the
    caller) rather than a fully sorted pair — the same narrow, accepted
    deadlock shape football's maybe_grant_referral_bonus_for_locked_user
    documents. Unlike football, no code path in RPG today locks a
    (referrer, then some other specific user) pair in the reverse order, so
    this risk is currently vacuous here, not just narrow — worth re-checking
    if a future feature ever introduces such a path."""
    if referred_user.referred_by_id is None or referred_user.referral_reward_granted:
        return

    locked_referrer = await lock_user_for_update(db, referred_user.referred_by_id)
    referrer_hero = await get_active_hero(db, locked_referrer)
    if referrer_hero is None:
        return

    referred_user.referral_reward_granted = True
    db.add(referred_user)

    await grant_hero_reward(
        db,
        referrer_hero.id,
        locked_referrer.id,
        REFERRAL_REWARD_XP,
        REFERRAL_REWARD_COINS,
        TransactionType.referral_reward,
        "Награда за приглашённого друга",
        related_object_type="user",
        related_object_id=referred_user.id,
    )
