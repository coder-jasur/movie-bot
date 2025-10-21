import asyncio

import asyncpg
from aiogram import Dispatcher, Bot
from aiogram.client.default import DefaultBotProperties
from aiogram_dialog import setup_dialogs

from logs.logger_conf import setup_logging
from src.app.common.bot_commands import create_bot_commands
from src.app.common.database_dsn import construct_postgresql_url
from src.app.core.config import Settings
from src.app.database.tables import create_database_tables
from src.app.dialog import dialog_register
from src.app.handlers import register_all_routers
from src.app.middleware import register_middleware


async def main():
    settings = Settings()

    dp = Dispatcher()

    dsn = construct_postgresql_url(settings)

    pool = await asyncpg.create_pool(
        dsn,
    )
    async with pool.acquire() as conn:
        await create_database_tables(conn)


    register_all_routers(dp, settings)
    dialog_register(dp)
    setup_dialogs(dp)

    register_middleware(dp, pool)

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    await create_bot_commands(bot, settings)

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        setup_logging("logs/logger.yml")
        asyncio.run(main())
    except Exception as e:
        print("ERROR", e)
