from typing import Any
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.kbd import Button, Row, SwitchTo, Cancel, Back, ScrollingGroup, Select
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.widgets.input import MessageInput
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database.queries.admin import AdminActions
from src.app.database.queries.user import UserActions
from src.app.bot.states.admin.dialogs import AdminManagementSG
from src.app.bot.settings.bot_commands import set_user_commands
from src.app.bot.common.i18n import lazy_gettext as _

async def get_admins_data(dialog_manager: DialogManager, **kwargs):
    session: AsyncSession = dialog_manager.middleware_data["session"]
    actions = AdminActions(session)
    admins = await actions.get_all_admins()
    
    return {
        "admins": admins,
        "admins_count": len(admins),
        "add_btn": _("➕ Qo'shish"),
        "back_btn": _("⬅️ Ortga")
    }

async def on_admin_selected(c: CallbackQuery, widget: Any, manager: DialogManager, item_id: str):
    manager.dialog_data["target_admin_id"] = int(item_id)
    await manager.switch_to(AdminManagementSG.admin_details)

async def get_admin_details(dialog_manager: DialogManager, **kwargs):
    session: AsyncSession = dialog_manager.middleware_data["session"]
    actions = AdminActions(session)
    admin_id = dialog_manager.dialog_data.get("target_admin_id")
    
    # Bazaviy interfeys matnlari har doim qaytarilishi shart
    data = {
        "no_admin": True,
        "tg_id": "-",
        "username": "-",
        "level_text": "-",
        "status_text": "-",
        "back_btn": _("⬅️ Ortga"),
        "toggle_status_btn": _("🔄 Statusni o'zgartirish"),
        "change_level_btn": _("🎖 Darajani o'zgartirish"),
        "delete_btn": _("🗑 O'chirish")
    }

    if not admin_id:
        return data

    admin = await actions.get_admin(admin_id)
    if not admin:
        return data
        
    data.update({
        "no_admin": False,
        "tg_id": admin.tg_id,
        "username": admin.username or "N/A",
        "level": admin.level,
        "level_text": _("Level 2 (Super)") if admin.level >= 2 else _("Level 1 (Admin)"),
        "status_text": _("Faol") if admin.is_active else _("Nofaol")
    })
    return data

async def on_id_username_input(m: Message, widget: Any, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    actions = AdminActions(session)
    
    query = m.text.strip()
    user = await actions.find_user_by_username_or_id(query)
    
    if not user:
        await m.answer(str(_("❌ Foydalanuvchi topilmadi. Avval botga start bosgan bo'lishi kerak.")))
        return
        
    manager.dialog_data["new_admin_id"] = user.tg_id
    manager.dialog_data["new_admin_username"] = user.username
    await manager.switch_to(AdminManagementSG.choose_level)

async def get_new_admin_data(dialog_manager: DialogManager, **kwargs):
    return {
        "new_admin_id": dialog_manager.dialog_data.get("new_admin_id"),
        "new_admin_username": dialog_manager.dialog_data.get("new_admin_username") or "N/A",
        "back_btn": _("⬅️ Ortga"),
        "level_1_btn": _("Level 1 (Admin)"),
        "level_2_btn": _("Level 2 (Super)")
    }

async def add_new_admin(c: CallbackQuery, widget: Button, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    actions = AdminActions(session)
    
    tg_id = manager.dialog_data.get("new_admin_id")
    username = manager.dialog_data.get("new_admin_username")
    level = 2 if widget.widget_id == "level_2" else 1
    
    await actions.add_admin(tg_id, username, level)
    
    # Update admin commands
    user_actions = UserActions(session)
    user = await user_actions.get_user(tg_id)
    language_code = user.language_code if user and user.language_code else "uz"
    bot = manager.middleware_data["bot"]
    await set_user_commands(bot, tg_id, language_code, is_admin=True)

    await c.answer(str(_("✅ Admin muvaffaqiyatli qo'shildi.")))
    await manager.switch_to(AdminManagementSG.list_admins)

async def toggle_admin_status(c: CallbackQuery, widget: Button, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    actions = AdminActions(session)
    admin_id = manager.dialog_data.get("target_admin_id")
    admin = await actions.get_admin(admin_id)
    
    await actions.update_admin(admin_id, is_active=not admin.is_active)

    # Update commands based on new status
    user_actions = UserActions(session)
    user = await user_actions.get_user(admin_id)
    language_code = user.language_code if user and user.language_code else "uz"
    bot = manager.middleware_data["bot"]
    await set_user_commands(bot, admin_id, language_code, is_admin=not admin.is_active)

    await c.answer(str(_("✅ Status o'zgartirildi.")))

async def change_admin_level(c: CallbackQuery, widget: Button, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    actions = AdminActions(session)
    admin_id = manager.dialog_data.get("target_admin_id")
    admin = await actions.get_admin(admin_id)
    
    new_level = 1 if admin.level >= 2 else 2
    await actions.update_admin(admin_id, level=new_level)
    await c.answer(str(_("✅ Daraja o'zgartirildi.")))

async def delete_admin(c: CallbackQuery, widget: Button, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    actions = AdminActions(session)
    admin_id = manager.dialog_data.get("target_admin_id")
    
    await actions.delete_admin(admin_id)

    # Remove admin commands
    user_actions = UserActions(session)
    user = await user_actions.get_user(admin_id)
    language_code = user.language_code if user and user.language_code else "uz"
    bot = manager.middleware_data["bot"]
    await set_user_commands(bot, admin_id, language_code, is_admin=False)

    await c.answer(str(_("✅ Admin o'chirildi.")))
    await manager.switch_to(AdminManagementSG.list_admins)

admin_management_dialog = Dialog(
    Window(
        Format(_("👥 <b>Adminlar ro'yxati</b> ({admins_count} ta):")),
        Row(
            Select(
                Format("{item.username} (L{item.level})"),
                id="s_admins",
                item_id_getter=lambda x: str(x.tg_id),
                items="admins",
                on_click=on_admin_selected,
            ),
        ),
        Row(
            SwitchTo(Format("{add_btn}"), id="add", state=AdminManagementSG.add_admin),
            Cancel(Format("{back_btn}")),
        ),
        state=AdminManagementSG.list_admins,
        getter=get_admins_data
    ),
    Window(
        Format(_("👤 <b>Yangi admin qo'shish</b>\n\nFoydalanuvchi ID yoki @username kiriting:")),
        MessageInput(on_id_username_input),
        SwitchTo(Format("{back_btn}"), id="back_to_list", state=AdminManagementSG.list_admins),
        state=AdminManagementSG.add_admin,
        getter=get_new_admin_data
    ),
    Window(
        Format(_("🎖 <b>Darajani tanlang:</b>\n\nFoydalanuvchi: {new_admin_username} ({new_admin_id})")),
        Row(
            Button(Format("{level_1_btn}"), id="level_1", on_click=add_new_admin),
            Button(Format("{level_2_btn}"), id="level_2", on_click=add_new_admin),
        ),
        SwitchTo(Format("{back_btn}"), id="back_to_add", state=AdminManagementSG.add_admin),
        state=AdminManagementSG.choose_level,
        getter=get_new_admin_data
    ),
    Window(
        Format(_("👤 <b>Admin ma'lumotlari:</b>\n\n🆔 ID: <code>{tg_id}</code>\n👤 Username: @{username}\n🎖 Daraja: {level_text}\n🔘 Status: {status_text}")),
        Row(
            Button(Format("{toggle_status_btn}"), id="toggle_status", on_click=toggle_admin_status),
            Button(Format("{change_level_btn}"), id="change_level", on_click=change_admin_level),
        ),
        Button(Format("{delete_btn}"), id="delete", on_click=delete_admin),
        SwitchTo(Format("{back_btn}"), id="back_to_list_details", state=AdminManagementSG.list_admins),
        state=AdminManagementSG.admin_details,
        getter=get_admin_details
    )
)
