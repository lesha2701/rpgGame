from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

import db
from config import get_bot_settings
from keyboards import invite_keyboard, open_app_keyboard

router = Router(name="user")
router.message.filter(F.chat.type == "private")
settings = get_bot_settings()

HELP_TEXT = (
    "⚔ <b>Vardren</b> — собери героя, отправляйся в поход и сражайся с врагами!\n\n"
    "<b>Команды:</b>\n"
    "/start — открыть игру\n"
    "/profile — показать свой профиль\n"
    "/invite — пригласить друга\n"
    "/help — это сообщение\n\n"
    "Нажми кнопку ниже, чтобы открыть приложение."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    # A referral deep link (t.me/<bot>?start=ref_<id>, see cmd_invite below)
    # arrives here as this payload — the Web App URL gets ?ref=<id> appended
    # so rpg-frontend's useSession picks it up from window.location.search
    # and forwards it as X-Referral-Code (see rpg-frontend/src/hooks/
    # useSession.ts) exactly like the football app's own App.tsx does.
    payload = message.text.split(maxsplit=1)[1] if message.text and " " in message.text else None

    text = (
        f"Приветствую, {message.from_user.first_name}! 👋\n\n"
        "Добро пожаловать в <b>Vardren</b> — создай героя, прокачивай его, "
        "проходи кампанию по землям королевства, сражайся на арене и охотся за сокровищами.\n\n"
        "Нажми кнопку ниже, чтобы начать 👇"
    )

    keyboard = open_app_keyboard()
    if payload and payload.startswith("ref_"):
        text += "\n\n🎉 Ты пришёл по приглашению друга!"
        referrer_id = payload[len("ref_"):]
        if referrer_id.isdigit():
            keyboard = open_app_keyboard(query=f"?ref={referrer_id}")

    await message.answer(text, reply_markup=keyboard)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=open_app_keyboard())


@router.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    user = await db.get_user_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer(
            "Ты ещё не зарегистрирован. Открой приложение, чтобы создать профиль 👇",
            reply_markup=open_app_keyboard(),
        )
        return

    hero = await db.get_hero_summary(user["id"])
    stats = await db.get_profile_stats(user["id"])

    text = f"👤 <b>{user['first_name'] or user['username'] or 'Игрок'}</b>\n\n"
    if hero:
        text += f"⚔ Герой: {hero['hero_name']}, уровень {hero['level']}\n"
    else:
        text += "⚔ Герой ещё не создан\n"
    text += (
        f"💰 Баланс: {user['balance']} монет\n"
        f"🗺 Узлов кампании пройдено: {stats['campaign_nodes_cleared']}\n"
        f"🏆 Побед на арене: {stats['arena_wins']}\n"
    )
    await message.answer(text, reply_markup=open_app_keyboard("/profile"))


@router.message(Command("invite"))
async def cmd_invite(message: Message) -> None:
    deep_link = f"https://t.me/{settings.telegram_bot_username}?start=ref_{message.from_user.id}"
    await message.answer(
        f"Пригласи друзей в Vardren!\n\n🔗 {deep_link}", reply_markup=invite_keyboard(deep_link)
    )
