from aiogram import Dispatcher, Router

from src.app.dialog.dialogs import op_dialog, channel_menu_dialog, add_channel_dialog


def dialog_register(dp: Dispatcher):
    dialog_register_router = Router()

    dialog_register_router.include_router(op_dialog)
    dialog_register_router.include_router(channel_menu_dialog)

    dp.include_router(dialog_register_router)