from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode

from src.app.bot.states.admin.dialogs import AdminMenuSG

admin_commands_router = Router()

@admin_commands_router.message(Command("admin_menu"))
async def admin_main_menu(message: Message, dialog_manager: DialogManager):
    await dialog_manager.start(AdminMenuSG.menu, mode=StartMode.RESET_STACK)





