from aiogram import Router, F

from src.app.core.config import Settings
from src.app.dialog import add_channel_dialog
from src.app.handlers.admin.add_movie.add_movie import add_movie_router
from src.app.handlers.admin.add_movie.feature_films import feature_films_router
from src.app.handlers.admin.add_movie.mini_series import mini_series_router
from src.app.handlers.admin.add_movie.series import series_router
from src.app.handlers.admin.broadcast import broadcater_router
from src.app.handlers.admin.commands import admin_commands_router
from src.app.handlers.admin.mandatory_subs import mandatory_subs_router
from src.app.handlers.admin.remove_movie.remove_movie import delete_router


def register_admin_rouetrs(router: Router, settings: Settings):
    admins_id = []
    for admin in settings.admins_ids:
        admins_id.append(int(admin))
    admin_register_router = Router()
    admin_register_router.message.filter(F.from_user.id.in_(admins_id))
    admin_register_router.callback_query.filter(F.from_user.id.in_(admins_id))


    admin_register_router.include_router(admin_commands_router)
    admin_register_router.include_router(mandatory_subs_router)
    admin_register_router.include_router(broadcater_router)
    admin_register_router.include_router(add_movie_router)
    admin_register_router.include_router(delete_router)
    admin_register_router.include_router(feature_films_router)
    admin_register_router.include_router(mini_series_router)
    admin_register_router.include_router(series_router)

    admin_register_router.include_router(add_channel_dialog)
    router.include_router(admin_register_router)
