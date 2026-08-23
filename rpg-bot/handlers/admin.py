from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import db
from config import get_bot_settings
from keyboards import open_app_keyboard

router = Router(name="admin")
settings = get_bot_settings()

# Quick mobile admin actions via the bot, alongside rpg-frontend's full
# JWT-based /admin/* web panel (same split as the football app: bot
# commands for on-the-go actions, the web panel for everything else) —
# not a replacement for it. No /give_card here (unlike the football
# bot's give_card): RPG's grantable content (items by tier/rarity,
# campaign progress) doesn't reduce to a single unambiguous "name" lookup
# the way football's one-player-per-name catalog does — use the web
# panel for that.


def _is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.admin_ids


async def _resolve_target(arg: str):
    arg = arg.lstrip("@")
    if arg.isdigit():
        return await db.get_user_by_telegram_id(int(arg))
    return await db.get_user_by_username(arg)


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа к административным командам.")
        return
    await message.answer(
        "🛠 <b>Панель администратора</b>\n\n"
        "/give_coins @user 100 [причина] — выдать монеты\n"
        "/ban @user — заблокировать\n"
        "/unban @user — разблокировать\n"
        "/stats — статистика проекта\n\n"
        "Полная административная панель доступна в приложении.",
        reply_markup=open_app_keyboard("/admin"),
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа к административным командам.")
        return
    stats = await db.get_stats()
    text = (
        "📊 <b>Статистика Vardren</b>\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"⚔ Героев создано: {stats['total_heroes']}\n"
        f"🗺 Побед в кампании: {stats['total_campaign_clears']}\n"
        f"🏆 Боёв на арене: {stats['total_arena_matches']}\n"
        f"💰 Монет в обороте: {stats['coins_in_circulation']}\n"
    )
    await message.answer(text)


@router.message(Command("give_coins"))
async def cmd_give_coins(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа к административным командам.")
        return
    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 3 or not parts[2].lstrip("-").isdigit():
        await message.answer("Использование: /give_coins @username 100 [причина]")
        return

    target = await _resolve_target(parts[1])
    if target is None:
        await message.answer("Пользователь не найден.")
        return

    amount = int(parts[2])
    description = parts[3] if len(parts) > 3 else "Выдано администратором через бота"
    updated = await db.give_coins(target["telegram_id"], amount, description)
    await message.answer(f"✅ Баланс {target['username'] or target['telegram_id']} теперь: {updated['balance']} монет.")


@router.message(Command("ban"))
async def cmd_ban(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа к административным командам.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /ban @username")
        return
    target = await _resolve_target(parts[1])
    if target is None:
        await message.answer("Пользователь не найден.")
        return
    await db.set_ban_status(target["telegram_id"], True)
    await message.answer(f"🚫 Пользователь {target['username'] or target['telegram_id']} заблокирован.")


@router.message(Command("unban"))
async def cmd_unban(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа к административным командам.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /unban @username")
        return
    target = await _resolve_target(parts[1])
    if target is None:
        await message.answer("Пользователь не найден.")
        return
    await db.set_ban_status(target["telegram_id"], False)
    await message.answer(f"✅ Пользователь {target['username'] or target['telegram_id']} разблокирован.")
