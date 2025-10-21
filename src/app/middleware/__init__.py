import asyncpg
from aiogram import Dispatcher

from src.app.middleware.database_pool import DatabaseMiddleware


def register_middleware(dp: Dispatcher, pool: asyncpg.Pool):


    data_pase_pool = DatabaseMiddleware(pool)
    dp.message.outer_middleware(data_pase_pool)
    dp.callback_query.outer_middleware(data_pase_pool)
    dp.chat_member.outer_middleware(data_pase_pool)


