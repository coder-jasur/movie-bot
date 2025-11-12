import asyncpg
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from src.app.database.queries.channels import ChannelActions
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
        f"<b>👋 Salom {message.from_user.first_name or message.from_user.last_name or message.from_user.full_name}</b>\n\n"
        f"<b>Botimizga xush kelibsiz.</b>\n\n"
        f"<b>🍿 Kino kodini yuboring: </b>",
    )
