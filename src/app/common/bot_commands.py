from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat

from src.app.core.config import Settings


async def create_bot_commands(bot: Bot, settings: Settings):
    await bot.set_my_commands(
        [
            BotCommand(command="/start", description="Запустить бота"),
            BotCommand(command="/favorites", description="Коллекция любимых фильмов")
        ]
    )
    for admin_id in settings.admins_ids:
        scope = BotCommandScopeChat(chat_id=int(admin_id))
        await bot.set_my_commands(
            [
                BotCommand(command="/start", description="Запустить бота"),
                BotCommand(command="/favorites", description="Коллекция любимых фильмов"),
                BotCommand(command="/admin_menu", description="Админ меню")
            ],
            scope=scope
        )
