from aiogram import Dispatcher, Router

from src.app.core.config import Settings
from src.app.dialog import add_channel_dialog
from src.app.handlers.admin import register_admin_rouetrs
from src.app.handlers.admin.check import check_sub_router
from src.app.handlers.admin.check_sub_channel import check_channel_sub_router
from src.app.handlers.start import start_router
from src.app.handlers.user.favorite_movies import favorite_movies_router
from src.app.handlers.user.movie_by_code import send_movie_by_code_router
from src.app.handlers.user.player import player_router


def register_all_routers(dp: Dispatcher, settings: Settings):
    main_router = Router()

    register_admin_rouetrs(main_router, settings)
    main_router.include_router(check_sub_router)
    main_router.include_router(check_channel_sub_router)
    main_router.include_router(start_router)
    main_router.include_router(favorite_movies_router)
    main_router.include_router(player_router)
    main_router.include_router(send_movie_by_code_router)
    dp.include_router(main_router)
