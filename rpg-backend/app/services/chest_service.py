"""Chest opening — structurally adapted from the football app's
app/services/pack_service.py (roll_rarities, pick_random_player, open_pack):
same weighted-random + guaranteed-minimum-rarity roll, same "pick a random
matching row, fall back if none configured" item selection, same two-layer
idempotency (early lookup + commit-time IntegrityError catch), same debit-
then-grant transaction shape. Adapted, not copied line-for-line: a Chest
grants exactly one item (not N cards).

Chests no longer carry their own Tier (removed in a later pass, see
Chest's docstring) — a chest's reward tier is capped by the *opening
hero's own* tier (item_progression.equipment_tier_for_level(hero.level)),
uniformly at random across every tier from 1 up to that cap. This also
means there is no more hero-level gate on which chests can be opened at
all — any hero can open any chest they can afford; a low-tier hero simply
never rolls above their own tier's items regardless of which chest they
buy. Chests differ from each other only by price/rarity_probabilities/
guaranteed_min_rarity now."""

import random
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.chest import Chest, ChestRarityProbability
from app.models.chest_opening import ChestOpening
from app.models.enums import RARITY_ORDER, Rarity, TransactionType
from app.models.item_template import ItemTemplate
from app.models.user import User
from app.models.user_hero import UserHero
from app.models.user_item import UserItem
from app.schemas.chest import ChestOpenResult, ChestOut, ChestRewardOut, ChestSummaryOut
from app.services.inventory_service import item_template_to_out
from app.services.progression import equipment_tier_for_level
from app.services.referral_service import maybe_grant_referral_reward
from app.services.wallet_service import debit_coins, lock_user_for_update


async def _get_chest_or_404(db: AsyncSession, chest_id: int) -> Chest:
    chest = await db.get(Chest, chest_id)
    if chest is None:
        raise NotFoundError("Chest not found")
    return chest


def _assert_chest_available(chest: Chest) -> None:
    if not chest.is_active:
        raise ConflictError("This chest is not currently available")


def roll_rarity(
    probabilities: list[ChestRarityProbability], guaranteed_min_rarity: Optional[Rarity]
) -> Rarity:
    """Single-item version of pack_service.roll_rarities (chests always
    grant exactly one item, so there's no card_count/list-of-rolls to
    manage) — same weighted random.choices + guaranteed-minimum override:
    if the roll doesn't meet the minimum, reroll among whichever configured
    rarities do (or force the minimum itself if none are configured at or
    above it)."""
    rarities = [p.rarity for p in probabilities]
    weights = [float(p.probability) for p in probabilities]
    if not rarities or sum(weights) <= 0:
        rarities, weights = [Rarity.common], [1.0]

    rolled = random.choices(rarities, weights=weights, k=1)[0]

    if guaranteed_min_rarity is not None and RARITY_ORDER[rolled] < RARITY_ORDER[guaranteed_min_rarity]:
        min_order = RARITY_ORDER[guaranteed_min_rarity]
        eligible = [(r, w) for r, w in zip(rarities, weights) if RARITY_ORDER[r] >= min_order]
        if not eligible:
            eligible = [(guaranteed_min_rarity, 1.0)]
        rolled = random.choices([r for r, _ in eligible], weights=[w for _, w in eligible], k=1)[0]

    return rolled


async def pick_random_item_template(db: AsyncSession, max_tier: int, rarity: Rarity) -> ItemTemplate:
    """max_tier (the opening hero's own tier) is a hard ceiling, never
    relaxed upward (a hero must never receive an item above their own
    tier) — only the rarity falls back, exactly mirroring
    pack_service.pick_random_player's fallback shape but with a tier
    ceiling instead of a fixed tier."""
    result = await db.execute(
        select(ItemTemplate)
        .where(ItemTemplate.tier <= max_tier, ItemTemplate.rarity == rarity, ItemTemplate.is_active.is_(True))
        .order_by(func.random())
        .limit(1)
    )
    template = result.unique().scalar_one_or_none()
    if template is None:
        result = await db.execute(
            select(ItemTemplate)
            .where(ItemTemplate.tier <= max_tier, ItemTemplate.is_active.is_(True))
            .order_by(func.random())
            .limit(1)
        )
        template = result.unique().scalar_one_or_none()
    if template is None:
        raise ConflictError(f"No active items configured at tier {max_tier} or below; cannot open this chest")
    return template


def _chest_to_summary(chest: Chest) -> ChestSummaryOut:
    return ChestSummaryOut(id=chest.id, name=chest.name)


async def _build_open_result(db: AsyncSession, opening: ChestOpening, balance: int) -> ChestOpenResult:
    chest = await _get_chest_or_404(db, opening.chest_id)
    user_item = await db.get(UserItem, opening.reward_user_item_id)
    assert user_item is not None
    template_out = item_template_to_out(user_item.item_template)
    return ChestOpenResult(
        opening_id=opening.id,
        chest=_chest_to_summary(chest),
        reward=ChestRewardOut(
            item_id=user_item.id,
            item_template_id=template_out.id,
            name=template_out.name,
            slot=template_out.slot,
            tier=template_out.tier,
            rarity=template_out.rarity,
            image_path=template_out.image_path,
            stats=template_out.stats,
            affixes=template_out.affixes,
        ),
        balance=balance,
    )


async def open_chest(
    db: AsyncSession, user: User, hero: UserHero, chest_id: int, idempotency_key: Optional[str]
) -> ChestOpenResult:
    if idempotency_key:
        existing = (
            await db.execute(
                select(ChestOpening).where(
                    ChestOpening.user_id == user.id, ChestOpening.idempotency_key == idempotency_key
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return await _build_open_result(db, existing, user.balance)

    chest = await _get_chest_or_404(db, chest_id)
    _assert_chest_available(chest)

    max_tier = equipment_tier_for_level(hero.level)

    locked_user = await lock_user_for_update(db, user.id)

    await debit_coins(
        db,
        locked_user,
        chest.price,
        TransactionType.chest_purchase,
        f"Открытие «{chest.name}»",
        related_object_type="chest",
        related_object_id=chest.id,
    )

    rarity = roll_rarity(chest.rarity_probabilities, chest.guaranteed_min_rarity)
    template = await pick_random_item_template(db, max_tier, rarity)

    user_item = UserItem(owner_user_id=locked_user.id, item_template_id=template.id, slot=template.slot)
    db.add(user_item)
    await db.flush()

    opening = ChestOpening(
        user_id=locked_user.id,
        chest_id=chest.id,
        reward_user_item_id=user_item.id,
        price_paid=chest.price,
        idempotency_key=idempotency_key,
        created_at=datetime.now(timezone.utc),
    )
    db.add(opening)

    # Stage 10: any successful chest opening — paid or free, whichever
    # tier — is the trigger for the referrer's one-time reward, exactly
    # like the football app's own pack_service (open_pack AND
    # claim_free_pack/grant_bonus_pack_opening all funnel into the same
    # check). RPG only needs one call site because RPG only has one
    # chest-opening function to begin with. No-ops silently for the
    # overwhelming majority of openings (no referrer, or already granted).
    await maybe_grant_referral_reward(db, locked_user)

    try:
        await db.commit()
    except IntegrityError:
        # Same race as pack_service.open_pack: two concurrent requests with
        # the same idempotency key — the loser rolls back and returns the
        # winner's already-committed result instead of double-charging.
        await db.rollback()
        if idempotency_key:
            existing = (
                await db.execute(
                    select(ChestOpening).where(
                        ChestOpening.user_id == user.id, ChestOpening.idempotency_key == idempotency_key
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return await _build_open_result(db, existing, user.balance)
        raise

    await db.refresh(locked_user)
    return await _build_open_result(db, opening, locked_user.balance)


async def list_chests(db: AsyncSession) -> list[Chest]:
    result = await db.execute(select(Chest).where(Chest.is_active.is_(True)).order_by(Chest.sort_order))
    return list(result.unique().scalars().all())


def chest_to_out(chest: Chest) -> ChestOut:
    return ChestOut(
        id=chest.id,
        slug=chest.slug,
        name=chest.name,
        description=chest.description,
        price=chest.price,
        image_path=chest.image_path,
        guaranteed_min_rarity=chest.guaranteed_min_rarity.value if chest.guaranteed_min_rarity else None,
        is_active=chest.is_active,
        rarity_probabilities=[
            {"rarity": p.rarity.value, "probability": float(p.probability)} for p in chest.rarity_probabilities
        ],
    )


async def list_openings(db: AsyncSession, user_id: int, limit: int = 50) -> list[ChestOpening]:
    result = await db.execute(
        select(ChestOpening)
        .where(ChestOpening.user_id == user_id)
        .order_by(ChestOpening.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
