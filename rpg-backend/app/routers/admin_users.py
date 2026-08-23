"""Admin user search/detail/moderation — the first admin router that isn't
a catalog CRUD resource. Read side reuses profile_service.get_statistics
(Stage 11) rather than re-deriving the same aggregates a second way. Coin
grants reuse wallet_service's existing lock+credit pattern (same one every
coin-granting code path in this app already uses) rather than writing a
new one."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin
from app.core.exceptions import ConflictError, NotFoundError
from app.database import get_db
from app.models.enums import TransactionType
from app.models.hero_template import HeroTemplate
from app.models.user import User
from app.models.user_hero import UserHero
from app.schemas.admin_user import (
    AdminUserDetailOut,
    AdminUserListOut,
    AdminUserStatsOut,
    AdminUserSummaryOut,
    DeductCoinsRequest,
    GrantCoinsRequest,
)
from app.services.profile_service import get_statistics
from app.services.wallet_service import credit_coins, debit_coins, lock_user_for_update

router = APIRouter(dependencies=[Depends(get_current_admin)])


def _summary_row_to_out(user: User, hero_name: str | None, hero_level: int | None) -> AdminUserSummaryOut:
    return AdminUserSummaryOut(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        balance=user.balance,
        is_admin=user.is_admin,
        is_banned=user.is_banned,
        created_at=user.created_at.isoformat(),
        hero_name=hero_name,
        hero_level=hero_level,
    )


def _base_query():
    return (
        select(User, HeroTemplate.name, UserHero.level)
        .outerjoin(UserHero, UserHero.id == User.active_hero_id)
        .outerjoin(HeroTemplate, HeroTemplate.id == UserHero.hero_template_id)
    )


@router.get("", response_model=AdminUserListOut)
async def list_users(
    search: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = _base_query()
    count_query = select(func.count(User.id))

    if search:
        conditions = [User.username.ilike(f"%{search}%")]
        if search.isdigit():
            conditions.append(User.telegram_id == int(search))
        filter_clause = or_(*conditions)
        query = query.where(filter_clause)
        count_query = count_query.where(filter_clause)

    total = (await db.execute(count_query)).scalar_one()
    rows = (await db.execute(query.order_by(User.id).limit(limit).offset(offset))).all()

    return AdminUserListOut(
        users=[_summary_row_to_out(u, name, level) for u, name, level in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=AdminUserStatsOut)
async def get_user_stats(db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(
                select(func.count(User.id)).scalar_subquery(),
                select(func.count(User.id)).where(User.is_banned.is_(True)).scalar_subquery(),
                select(func.count(User.id)).where(User.is_admin.is_(True)).scalar_subquery(),
                select(func.count(User.id)).where(User.active_hero_id.is_not(None)).scalar_subquery(),
                select(func.coalesce(func.sum(User.balance), 0)).scalar_subquery(),
            )
        )
    ).one()
    total_users, banned_users, admin_users, users_with_hero, total_balance = row
    return AdminUserStatsOut(
        total_users=total_users,
        banned_users=banned_users,
        admin_users=admin_users,
        users_with_hero=users_with_hero,
        total_balance_in_circulation=total_balance,
    )


async def _assert_user_exists(db: AsyncSession, user_id: int) -> None:
    # lock_user_for_update uses scalar_one(), which raises NoResultFound
    # (an ugly 500, not a clean 404) for a missing id — check existence
    # first with a plain, lock-free get() before taking the row lock.
    if await db.get(User, user_id) is None:
        raise NotFoundError("User not found")


@router.get("/{user_id}", response_model=AdminUserDetailOut)
async def get_user_detail(user_id: int, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(_base_query().where(User.id == user_id))).first()
    if row is None:
        raise NotFoundError("User not found")
    user, hero_name, hero_level = row
    statistics = await get_statistics(db, user_id)
    summary = _summary_row_to_out(user, hero_name, hero_level)
    return AdminUserDetailOut(**summary.model_dump(), statistics=statistics)


@router.post("/{user_id}/grant-coins", response_model=AdminUserSummaryOut)
async def grant_coins(user_id: int, payload: GrantCoinsRequest, db: AsyncSession = Depends(get_db)):
    await _assert_user_exists(db, user_id)
    user = await lock_user_for_update(db, user_id)
    await credit_coins(db, user, payload.amount, TransactionType.admin_grant, description=payload.description)
    await db.commit()

    row = (await db.execute(_base_query().where(User.id == user_id))).first()
    refreshed, hero_name, hero_level = row
    return _summary_row_to_out(refreshed, hero_name, hero_level)


@router.post("/{user_id}/deduct-coins", response_model=AdminUserSummaryOut)
async def deduct_coins(user_id: int, payload: DeductCoinsRequest, db: AsyncSession = Depends(get_db)):
    await _assert_user_exists(db, user_id)
    user = await lock_user_for_update(db, user_id)
    await debit_coins(db, user, payload.amount, TransactionType.admin_deduct, description=payload.description)
    await db.commit()

    row = (await db.execute(_base_query().where(User.id == user_id))).first()
    refreshed, hero_name, hero_level = row
    return _summary_row_to_out(refreshed, hero_name, hero_level)


@router.post("/{user_id}/toggle-ban", response_model=AdminUserSummaryOut)
async def toggle_ban(user_id: int, db: AsyncSession = Depends(get_db)):
    await _assert_user_exists(db, user_id)
    user = await lock_user_for_update(db, user_id)
    if user.is_admin:
        raise ConflictError("Cannot ban an admin user")

    user.is_banned = not user.is_banned
    db.add(user)
    await db.commit()

    row = (await db.execute(_base_query().where(User.id == user_id))).first()
    refreshed, hero_name, hero_level = row
    return _summary_row_to_out(refreshed, hero_name, hero_level)
