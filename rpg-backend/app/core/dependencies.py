from typing import Optional

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import TelegramAuthError, TelegramUser, decode_admin_token, validate_init_data
from app.database import get_db
from app.models.user import User

settings = get_settings()


async def _get_or_create_user(
    db: AsyncSession, tg_user: TelegramUser, referral_code: Optional[str] = None
) -> User:
    result = await db.execute(select(User).where(User.telegram_id == tg_user.id))
    user = result.scalar_one_or_none()
    is_admin_now = tg_user.id in settings.admin_ids

    if user is None:
        try:
            # SAVEPOINT (not a plain rollback) so a lost race — several
            # concurrent first-load requests for a brand-new telegram_id —
            # only undoes this one failed insert; same pattern as the
            # football app's core/dependencies.py.
            async with db.begin_nested():
                user = User(
                    telegram_id=tg_user.id,
                    username=tg_user.username,
                    first_name=tg_user.first_name,
                    last_name=tg_user.last_name,
                    is_admin=is_admin_now,
                )
                db.add(user)
                await db.flush()
        except IntegrityError:
            # Lost the race — the winner's row (and its referral link, if
            # any, already committed by that request) is what we want, not
            # a second attempt at setting it. Falls through to the
            # existing-user path below, which never touches referred_by_id.
            result = await db.execute(select(User).where(User.telegram_id == tg_user.id))
            user = result.scalar_one()
        else:
            # Referral code = the referrer's raw telegram_id (no separate
            # generated code/table — same principle as the football app's
            # X-Referral-Code). Only reachable here, on the winning insert:
            # the existing-user update path below never references
            # referred_by_id at all, which is what makes the link immutable
            # after creation without needing an explicit "already set" guard.
            # A missing/malformed/unknown/self-referencing code silently
            # results in no link — never an error, registration always
            # succeeds regardless of what this client-supplied header says.
            if referral_code:
                try:
                    ref_telegram_id = int(referral_code)
                except ValueError:
                    ref_telegram_id = None
                if ref_telegram_id is not None and ref_telegram_id != tg_user.id:
                    referrer_result = await db.execute(select(User).where(User.telegram_id == ref_telegram_id))
                    referrer = referrer_result.scalar_one_or_none()
                    if referrer is not None:
                        user.referred_by_id = referrer.id
        await db.commit()
        await db.refresh(user)
        return user

    changed = False
    if user.username != tg_user.username:
        user.username = tg_user.username
        changed = True
    if user.first_name != tg_user.first_name:
        user.first_name = tg_user.first_name
        changed = True
    if user.last_name != tg_user.last_name:
        user.last_name = tg_user.last_name
        changed = True
    if user.is_admin != is_admin_now:
        user.is_admin = is_admin_now
        changed = True
    if changed:
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_mode: Optional[str] = Header(default=None, alias="X-Dev-Mode"),
    x_referral_code: Optional[str] = Header(default=None, alias="X-Referral-Code"),
) -> User:
    if x_telegram_init_data:
        try:
            tg_user = validate_init_data(x_telegram_init_data, settings.telegram_bot_token)
        except TelegramAuthError as exc:
            raise UnauthorizedError(f"Telegram auth failed: {exc}") from exc
    elif settings.dev_mode and x_dev_mode == "true":
        tg_user = TelegramUser(id=settings.dev_user_telegram_id, username="dev_user", first_name="Dev", last_name="User")
    else:
        raise UnauthorizedError("Missing Telegram init data")

    user = await _get_or_create_user(db, tg_user, referral_code=x_referral_code)
    if user.is_banned:
        raise ForbiddenError("This account has been banned")
    return user


async def get_current_admin(
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
) -> User:
    """Ported verbatim from the football app's core/dependencies.py: bearer
    admin JWT (minted at /auth/session), re-checked against settings.admin_ids
    on every request (not just trusted from the token/is_admin column alone)
    so revoking someone from RPG_ADMIN_TELEGRAM_IDS invalidates already-
    issued tokens without needing to track/revoke them individually."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing admin bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_admin_token(token)
    except TelegramAuthError as exc:
        raise UnauthorizedError("Invalid admin token") from exc

    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("Admin user not found")
    if user.telegram_id not in settings.admin_ids or not user.is_admin:
        raise ForbiddenError("Admin access required")
    if user.is_banned:
        raise ForbiddenError("This account has been banned")
    return user
