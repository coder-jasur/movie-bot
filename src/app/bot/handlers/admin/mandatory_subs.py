from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager

from src.app.bot.states.admin.channel import OPMenu

mandatory_subs_router = Router()

@mandatory_subs_router.callback_query(F.data == "mandatory_subscriptions")
async def send_admin_menu(callback: CallbackQuery, dialog_manager: DialogManager):
    await dialog_manager.start(OPMenu.menu)

