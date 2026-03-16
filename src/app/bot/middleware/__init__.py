from sqlalchemy.ext.asyncio import async_sessionmaker
from aiogram import Dispatcher

from src.app.bot.middleware.database_pool import DatabaseMiddleware
from src.app.bot.middleware.i18n import CustomI18nMiddleware
from src.app.bot.middleware.vip_check import VIPExpiryMiddleware


def register_middleware(dp: Dispatcher, session_pool: async_sessionmaker) -> CustomI18nMiddleware:
    middleware = DatabaseMiddleware(session_pool)
    i18n_middleware = CustomI18nMiddleware(session_pool)
    vip_middleware = VIPExpiryMiddleware()
    
    dp.message.outer_middleware(middleware)
    dp.callback_query.outer_middleware(middleware)
    dp.chat_member.outer_middleware(middleware)
    
    dp.message.middleware(vip_middleware)
    dp.callback_query.middleware(vip_middleware)
    
    # I18n middleware must be set up before setup_dialogs so aiogram-dialog
    # can use it to render LazyProxy objects correctly.
    i18n_middleware.setup(dp)
    
    return i18n_middleware
