from aiogram import Dispatcher, Router

from src.app.core.config import Settings
from src.app.bot.handlers.admin import register_admin_routers
from src.app.bot.handlers.admin.check_sub_channel import check_channel_sub_router, sub_check_button_router
from src.app.bot.handlers.start import start_router
from src.app.bot.handlers.user.favorite_movies import favorite_movies_router
from src.app.bot.handlers.user.movie_search import movie_search_router
from src.app.bot.handlers.user.player import player_router
from src.app.bot.handlers.user.language import language_router
from src.app.bot.handlers.user.account import account_router


def register_all_routers(dp: Dispatcher, settings: Settings):
    main_router = Router()

    register_admin_routers(main_router, settings)
    
    # 1. Check button handler (must be first to handle 'check_sub' for everyone)
    main_router.include_router(sub_check_button_router)

    # 2. Mandatory subscription barrier (intercepts others if not subscribed)
    main_router.include_router(check_channel_sub_router)
    
    main_router.include_router(start_router)
    main_router.include_router(language_router)
    main_router.include_router(account_router)
    main_router.include_router(favorite_movies_router)
    main_router.include_router(player_router)
    # This should be last as it handles general text messages
    main_router.include_router(movie_search_router)
    dp.include_router(main_router)
    
    # Inject settings to handlers
    dp["settings"] = settings
