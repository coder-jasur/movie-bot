import asyncio
import logging
import sys
from pathlib import Path

import uvicorn
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from src.app.api.app import app

# Root yo'lini sozlash
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram_dialog import setup_dialogs

from logs.logger_conf import setup_logging
from src.app.bot.handlers import register_all_routers
from src.app.bot.middleware import register_middleware
from src.app.bot.settings.bot_commands import create_bot_commands
from src.app.core.config import load_config
from src.app.database.core import Base, Database
from src.app.database.database_backup import daily_database_sender


async def start_api():
    config = uvicorn.Config(
        app, host="0.0.0.0", port=8000, loop="asyncio", log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    try:
        settings = load_config()
        dp = Dispatcher()
        dsn = settings.construct_postgresql_url()
        db = Database(dsn)

        # DB jadvallarini tekshirish
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        dp["settings"] = settings
        dp["session_pool"] = db.session_factory
        register_middleware(dp, db.session_factory)
        register_all_routers(dp, settings)
        setup_dialogs(dp)

        session = AiohttpSession(
            api=TelegramAPIServer.from_url(settings.tg_api_server_url)
        )

        bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
            session=session,
        )

        # FastAPI state
        app.state.bot = bot
        app.state.dp = dp

        from src.app.api.webhook import router as webhook_router

        app.include_router(webhook_router, prefix=settings.webhook_path)

        asyncio.create_task(
            daily_database_sender(bot, settings.admins_ids, db.session_factory)
        )
        await create_bot_commands(bot, settings)

        if settings.use_webhook:
            webhook_url = f"{settings.webhook_url}{settings.webhook_path}"
            await bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
                allowed_updates=dp.resolve_used_update_types(),
            )
            print(f"WEBHOOK MODE: {webhook_url}")
            await start_api()
        else:
            print("POLLING MODE: Deleting webhook and starting...")
            await bot.delete_webhook()
            # Bir vaqtning o'zida ham polling, ham API ni ishga tushiramiz
            await asyncio.gather(dp.start_polling(bot), start_api())
    except Exception as e:
        print(f"\n❌ STARTUP ERROR: {e}")
        logging.exception(e)


if __name__ == "__main__":
    setup_logging("logs/logger.yml")
    asyncio.run(main())
