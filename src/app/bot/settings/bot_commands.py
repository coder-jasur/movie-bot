from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat

from src.app.core.config import Settings


COMMANDS = {
    "uz": [
        BotCommand(command="/start", description="Botni ishga tushirish"),
        BotCommand(command="/profile", description="Shaxsiy kabinet"),
        BotCommand(command="/favorites", description="Sevimli filmlar to'plami"),
        BotCommand(command="/language", description="Tilni o'zgartirish"),
    ],
    "ru": [
        BotCommand(command="/start", description="Запустить бота"),
        BotCommand(command="/profile", description="Личный кабинет"),
        BotCommand(command="/favorites", description="Список избранного"),
        BotCommand(command="/language", description="Сменить язык"),
    ],
    "en": [
        BotCommand(command="/start", description="Start the bot"),
        BotCommand(command="/profile", description="Personal profile"),
        BotCommand(command="/favorites", description="Favorites list"),
        BotCommand(command="/language", description="Change language"),
    ]
}

ADMIN_COMMANDS = {
    "uz": COMMANDS["uz"] + [BotCommand(command="/admin_menu", description="Admin menyu")],
    "ru": COMMANDS["ru"] + [BotCommand(command="/admin_menu", description="Админ меню")],
    "en": COMMANDS["en"] + [BotCommand(command="/admin_menu", description="Admin menu")]
}


async def set_user_commands(bot: Bot, user_id: int, language_code: str, is_admin: bool = False):
    """Sets commands for a specific user based on their language and admin status."""
    commands_dict = ADMIN_COMMANDS if is_admin else COMMANDS
    commands = commands_dict.get(language_code, commands_dict["uz"])
    
    scope = BotCommandScopeChat(chat_id=user_id)
    await bot.set_my_commands(commands, scope=scope)


async def create_bot_commands(bot: Bot, settings: Settings):
    # Set global commands for each language
    for lang, commands in COMMANDS.items():
        await bot.set_my_commands(commands, language_code=lang)
    
    # NOTE: Individual user/admin commands are now handled in 
    # start and language handlers by calling set_user_commands.
