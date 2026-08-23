from pydantic import BaseModel

from app.schemas.character import UserHeroOut


class UserMeOut(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    active_hero: UserHeroOut | None
    # str(telegram_id) — nothing generated or stored, see referral_service.py.
    referral_code: str
    # Derived COUNT of successful (reward-granted) referrals, never a column.
    referral_count: int


class SessionResponse(BaseModel):
    user: UserMeOut
    admin_token: str | None = None
