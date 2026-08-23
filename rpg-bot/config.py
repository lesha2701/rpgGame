from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """RPG_* env vars only — never the football app's TELEGRAM_BOT_TOKEN/
    DATABASE_URL/etc (see rpg-backend/app/config.py's own docstring for
    the same isolation rule). Structurally the football bot's config.py,
    trimmed to what this bot actually uses: no internal_api_secret/
    internal_backend_url (no Stars payments here — see bot.py's
    docstring), no chat-pack-specific settings."""

    model_config = SettingsConfigDict(env_file=".env.rpg.local", env_prefix="RPG_", extra="ignore")

    telegram_bot_token: str = "0:DEV"
    telegram_bot_username: str = "vardren_bot"
    admin_telegram_ids: str = ""
    mini_app_url: str = "http://localhost:5174"
    bot_mode: str = "polling"
    bot_webhook_url: str = ""
    bot_webhook_secret: str = "dev_webhook_secret"
    bot_webhook_port: int = 8082
    telegram_proxy_url: str = ""

    database_url: str = "postgresql://rpg_admin:rpg_dev_password_change_me@localhost:5437/rpg_game"

    @property
    def admin_ids(self) -> List[int]:
        return [int(x) for x in self.admin_telegram_ids.split(",") if x.strip()]

    @property
    def asyncpg_dsn(self) -> str:
        # asyncpg does not understand SQLAlchemy's "+asyncpg" dialect suffix.
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")


@lru_cache
def get_bot_settings() -> BotSettings:
    return BotSettings()
