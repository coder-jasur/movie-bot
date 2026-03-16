import asyncio
import datetime
import logging
import os

import aiofiles
from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.app.database.queries.user import UserActions

logger = logging.getLogger(__name__)


async def send_database_to_owner(bot: Bot, chat_ids: list[int], db_path: str):
    is_file_exists = await asyncio.to_thread(os.path.exists, db_path)

    if is_file_exists:
        db_file = FSInputFile(db_path)
        tasks = [
            asyncio.create_task(
                bot.send_document(
                    chat_id=chat_id, document=db_file, caption="📦 База Данных"
                )
            )
            for chat_id in chat_ids
        ]
        await asyncio.gather(*tasks)


async def daily_database_sender(
    bot: Bot, chat_ids: list[int], session_pool: async_sessionmaker
) -> None:
    while True:
        try:
            async with session_pool() as session:
                user_actions = UserActions(session)
                all_users = await user_actions.get_all_user()

            async with aiofiles.open("all_users.txt", "w", encoding="utf-8") as f:
                for user in all_users:
                    # user is now a User object, so we access .tg_id
                    await f.write(f"{user.tg_id}\n")

            now = datetime.datetime.now()
            target_time = now.replace(hour=0, minute=0, second=0, microsecond=0)

            if now >= target_time:
                target_time += datetime.timedelta(days=1)

            sleep_duration = (target_time - now).total_seconds()
            await asyncio.sleep(sleep_duration)

            await send_database_to_owner(bot, chat_ids, "all_users.txt")

        except Exception as e:
            logger.exception(e)
            # Sleep a bit to avoid rapid loop on error
            await asyncio.sleep(60)
