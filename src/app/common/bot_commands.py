from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat

from src.app.core.config import Settings


async def create_bot_commands(bot: Bot, settings: Settings):
    await bot.set_my_commands(
        [
            BotCommand(command="/start", description="Botni ishga tushirish"),
            BotCommand(command="/favorites", description="Sevimli filmlar to'plami")
        ]
    )
    for admin_id in settings.admins_ids:
        scope = BotCommandScopeChat(chat_id=int(admin_id))
        await bot.set_my_commands(
            [
                BotCommand(command="/start", description="Botni ishga tushirish"),
                BotCommand(command="/favorites", description="Sevimli filmlar to'plami"),
                BotCommand(command="/admin_menu", description="Admin menu")
            ],
            scope=scope
        )
