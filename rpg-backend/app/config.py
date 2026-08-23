from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.rpg.local", extra="ignore")

    # Telegram — this RPG deliberately reads its own env vars (RPG_*), never
    # the football app's TELEGRAM_BOT_TOKEN/DEV_MODE/etc. A real RPG bot
    # registration is not needed yet; only DEV_MODE auth is exercised until
    # a bot exists.
    telegram_bot_token: str = Field(default="0:DEV", validation_alias="RPG_TELEGRAM_BOT_TOKEN")
    dev_mode: bool = Field(default=False, validation_alias="RPG_DEV_MODE")
    dev_user_telegram_id: int = Field(default=999000001, validation_alias="RPG_DEV_USER_TELEGRAM_ID")
    environment: str = Field(default="development", validation_alias="RPG_ENVIRONMENT")

    # Database — deliberately named RPG_DATABASE_URL (never DATABASE_URL,
    # which is the football app's own variable in the same shell/host) and
    # has NO DEFAULT. If RPG_DATABASE_URL is unset, Settings() raises at
    # startup instead of silently falling back to anything — there is no
    # value this could quietly resolve to that would ever point at the
    # football app's database. See app/main.py for a second, redundant
    # guard on top of this.
    database_url: str = Field(validation_alias="RPG_DATABASE_URL")
    db_pool_size: int = Field(default=10, validation_alias="RPG_DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, validation_alias="RPG_DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, validation_alias="RPG_DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=1800, validation_alias="RPG_DB_POOL_RECYCLE")

    backend_port: int = Field(default=8100, validation_alias="RPG_BACKEND_PORT")
    cors_origins: str = Field(default="http://localhost:5174", validation_alias="RPG_CORS_ORIGINS")

    # Admin — same shape as the football app's (JWT minted at /auth/session
    # for telegram_ids in this list, checked again on every admin request in
    # get_current_admin so revoking an id invalidates already-issued tokens).
    jwt_secret: str = Field(default="dev_only_secret", validation_alias="RPG_JWT_SECRET")
    jwt_expire_minutes: int = Field(default=720, validation_alias="RPG_JWT_EXPIRE_MINUTES")
    admin_telegram_ids: str = Field(default="", validation_alias="RPG_ADMIN_TELEGRAM_IDS")

    @property
    def cors_origin_list(self) -> List[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def admin_ids(self) -> List[int]:
        return [int(x) for x in self.admin_telegram_ids.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
