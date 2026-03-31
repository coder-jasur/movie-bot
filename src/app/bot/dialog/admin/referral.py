from aiogram import Bot
from aiogram.types import CallbackQuery, ContentType, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Cancel, ScrollingGroup, Select, SwitchTo
from aiogram_dialog.widgets.text import Const, Format
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.common.i18n import lazy_gettext as _
from src.app.bot.states.admin.referral import ReferralSG
from src.app.database.queries.referral import ReferralActions


async def get_referrals(dialog_manager: DialogManager, **kwargs):
    session: AsyncSession = dialog_manager.middleware_data["session"]
    actions = ReferralActions(session)
    referrals = await actions.get_all_referrals()
    return {
        "referrals": referrals,
        "title": str(
            _("🔗 <b>Рефералы</b>\n\nВыберите из списка или создайте нового:")
        ),
        "add_ref": str(_("➕ Создать реферала")),
        "back": str(_("⬅️ Назад")),
    }


async def on_referral_selected(
    c: CallbackQuery, widget, manager: DialogManager, item_id: str
):
    manager.dialog_data["referral_id"] = int(item_id)
    await manager.switch_to(ReferralSG.view)


async def get_referral_details(dialog_manager: DialogManager, **kwargs):
    session: AsyncSession = dialog_manager.middleware_data["session"]
    bot: Bot = dialog_manager.middleware_data["bot"]
    referral_id = dialog_manager.dialog_data.get("referral_id")

    actions = ReferralActions(session)
    referral = await actions.get_referral(referral_id)

    if not referral:
        return {"referral": None, "bot_link": "N/A"}

    bot_info = await bot.get_me()
    bot_link = f"https://t.me/{bot_info.username}"

    # Evaluate proxy dynamically at runtime
    info_text = str(_("Referal info")).format(
        id=referral.referral_id,
        name=referral.name,
        joined_count=referral.joined_count,
        created_at=referral.created_at,
        link=bot_link,
    )

    return {
        "referral": referral,
        "bot_link": bot_link,
        "info": info_text,
        "delete": str(_("🗑 Удалить")),
        "back": str(_("⬅️ Назад")),
    }


async def get_add_texts(dialog_manager: DialogManager, **kwargs):
    return {
        "title": str(_("✏️ <b>Новый реферал:</b>\n\nВведите название:")),
        "cancel": str(_("❌ Отмена")),
    }


async def on_referral_created(message: Message, widget, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    actions = ReferralActions(session)
    await actions.create_referral(message.text)
    await message.answer(str(_("✅ Успешно создано!")))
    await manager.switch_to(ReferralSG.menu)


async def on_referral_delete(c: CallbackQuery, widget, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    referral_id = manager.dialog_data.get("referral_id")
    actions = ReferralActions(session)
    await actions.delete_referral(referral_id)
    await c.answer(str(_("✅ Удалено")))
    await manager.switch_to(ReferralSG.menu)


referral_dialog = Dialog(
    Window(
        Format("{title}"),
        ScrollingGroup(
            Select(
                Format("{item.name} | {item.joined_count}"),
                id="referral_select",
                item_id_getter=lambda x: x.referral_id,
                items="referrals",
                on_click=on_referral_selected,
            ),
            id="referrals_group",
            width=1,
            height=10,
            hide_pager=True,
        ),
        SwitchTo(Format("{add_ref}"), id="add_ref", state=ReferralSG.add),
        Cancel(Format("{back}"), id="back"),
        state=ReferralSG.menu,
        getter=get_referrals,
    ),
    Window(
        Format("{title}"),
        MessageInput(on_referral_created, content_types=ContentType.TEXT),
        SwitchTo(Format("{cancel}"), id="cancel_add", state=ReferralSG.menu),
        state=ReferralSG.add,
        getter=get_add_texts,
    ),
    Window(
        Format("{info}"),
        Button(Format("{delete}"), id="delete_ref", on_click=on_referral_delete),
        SwitchTo(Format("{back}"), id="back_list", state=ReferralSG.menu),
        state=ReferralSG.view,
        getter=get_referral_details,
    ),
)
