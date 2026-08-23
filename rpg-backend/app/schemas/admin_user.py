from pydantic import BaseModel, Field

from app.schemas.profile import ProfileStatisticsOut


class AdminUserSummaryOut(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    balance: int
    is_admin: bool
    is_banned: bool
    created_at: str
    hero_name: str | None
    hero_level: int | None


class AdminUserListOut(BaseModel):
    users: list[AdminUserSummaryOut]
    total: int
    limit: int
    offset: int


class AdminUserDetailOut(AdminUserSummaryOut):
    statistics: ProfileStatisticsOut


class AdminUserStatsOut(BaseModel):
    """Aggregate, computed live on every request (same 'derive, don't
    store' call as everywhere else in this backend) — no counters table."""

    total_users: int
    banned_users: int
    admin_users: int
    users_with_hero: int
    total_balance_in_circulation: int


class GrantCoinsRequest(BaseModel):
    amount: int = Field(gt=0)
    description: str = ""


class DeductCoinsRequest(BaseModel):
    amount: int = Field(gt=0)
    description: str = ""
