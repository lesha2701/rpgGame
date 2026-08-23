"""Vardren's Telegram bot — this is what actually launches the Mini App
(a `web_app` inline button, see keyboards.py) and is what
rpg-backend/app/core/security.py's initData HMAC validation authenticates
against (RPG_TELEGRAM_BOT_TOKEN must be the same bot on both sides).

Structurally the football app's bot.py (aiogram Dispatcher, polling/
webhook mode switch, background tasks list) — not copied verbatim,
trimmed to what Vardren's backend actually has to hook into: no
notification dispatcher (rpg-backend has no `notifications` table yet —
nothing produces rows for one to poll), no free-pack/chest reminder
(rpg-backend's free chest availability is derived from ChestOpening
timestamps, not a `notified` flag a dispatcher could check once and
mark — see free_chest_service.py), no Stars-payment relay (not built).
Both are straightforward to add once their backend half exists; adding
the polling loop first with nothing to feed it would just be dead code."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

import db
from config import get_bot_settings
from handlers import admin as admin_handlers
from handlers import user as user_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("vardren.bot")

settings = get_bot_settings()


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(admin_handlers.router)
    dp.include_router(user_handlers.router)
    return dp


def _make_bot() -> Bot:
    session = AiohttpSession(proxy=settings.telegram_proxy_url) if settings.telegram_proxy_url else None
    return Bot(token=settings.telegram_bot_token, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def run_polling() -> None:
    bot = _make_bot()
    dp = build_dispatcher()

    await db.get_pool()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Starting bot in polling mode")
        await dp.start_polling(bot)
    finally:
        await db.close_pool()
        await bot.session.close()


async def run_webhook() -> None:
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    bot = _make_bot()
    dp = build_dispatcher()

    await db.get_pool()

    await bot.set_webhook(settings.bot_webhook_url, secret_token=settings.bot_webhook_secret, drop_pending_updates=True)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=settings.bot_webhook_secret).register(app, path="/bot/webhook")
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.bot_webhook_port)
    logger.info("Starting bot in webhook mode on port %s", settings.bot_webhook_port)
    await site.start()

    try:
        await asyncio.Event().wait()
    finally:
        await db.close_pool()
        await bot.session.close()


def main() -> None:
    if settings.bot_mode == "webhook":
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
