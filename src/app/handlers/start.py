import asyncpg
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from src.app.database.queries.user import UserActions
from src.app.keyboards.inline import start_menu

start_router = Router()


@start_router.message(CommandStart())
async def start_bot(message: Message, pool: asyncpg.Pool):
    user_actions = UserActions(pool)
    user_data = await user_actions.get_user(message.from_user.id)
    if not user_data:
        await user_actions.add_user(
            message.from_user.id,
            message.from_user.username or message.from_user.first_name,

        )
    await message.answer(
        f"👋 Assalomu aleykum {message.from_user.first_name}\n\n"
        "👀 Film - Serila - Multfilm ko'rish uchun:\n\n"
        "1️⃣ Kanalga obuna bo'ling\n"
        "2⃣  Instagram yoki telegram kanalimizdan kerakli filmni tanlang👇\n"
        "3⃣  Botga film kodini yuboring✍️\n\n"
        "🎬 Eng so'nggi filmlar va seriallar! Faqat siz uchun! 🍿",
        reply_markup=start_menu
    )
