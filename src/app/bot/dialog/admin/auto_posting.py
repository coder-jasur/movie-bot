from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Cancel, Row, ScrollingGroup, Select, SwitchTo, Back
from aiogram_dialog.widgets.text import Const, Format
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.states.admin.dialogs import PostAutoPostingSG
from src.app.database.queries.post_channels import PostChannelActions
from src.app.bot.common.i18n import lazy_gettext as _

async def get_post_channels(dialog_manager: DialogManager, **kwargs):
    session: AsyncSession = dialog_manager.middleware_data["session"]
    actions = PostChannelActions(session)
    channels = await actions.get_all_post_channels()
    return {
        "channels": channels,
        "count": len(channels),
        "add_channel_label": _("➕ Kanal qo'shish"),
        "back_label": _("⬅️ Orqaga")
    }

async def on_channel_id_input(m: Message, widget, manager: DialogManager):
    # Support both ID and forward
    channel_id = None
    channel_name = "Kanal"
    channel_username = None

    if m.forward_from_chat:
        channel_id = m.forward_from_chat.id
        channel_name = m.forward_from_chat.title
        channel_username = m.forward_from_chat.username
    elif m.text:
        try:
            channel_id = int(m.text)
        except ValueError:
            await m.answer(str(_("❌ Iltimos, kanal ID raqamini yoki xabarni forward qilib yuboring.")))
            return
    else:
        await m.answer(str(_("❌ Iltimos, kanal ID raqamini yoki xabarni forward qilib yuboring.")))
        return

    session: AsyncSession = manager.middleware_data["session"]
    actions = PostChannelActions(session)
    
    # Check if already exists
    existing = await actions.get_post_channel(channel_id)
    if existing:
        await m.answer(str(_("⚠️ Bu kanal allaqachon qo'shilgan.")))
        return

    await actions.add_post_channel(channel_id, channel_name, channel_username)
    await m.answer(str(_("✅ Kanal muvaffaqiyatli qo'shildi.")))
    await manager.switch_to(PostAutoPostingSG.menu)

async def on_channel_click(c: CallbackQuery, widget, manager: DialogManager, item_id: str):
    manager.dialog_data["channel_id"] = int(item_id)
    await manager.switch_to(PostAutoPostingSG.channel_info)

async def get_channel_info(dialog_manager: DialogManager, **kwargs):
    session: AsyncSession = dialog_manager.middleware_data["session"]
    actions = PostChannelActions(session)
    channel_id = dialog_manager.dialog_data.get("channel_id")
    channel = await actions.get_post_channel(channel_id)
    if not channel:
        return {}
    
    is_active = channel.channel_status == "active"
    return {
        "channel": channel,
        "autopost_toggle_text": _("📢 Avtoposting: ✅") if is_active else _("📢 Avtoposting: ❌"),
        "delete_label": _("🗑 O'chirish"),
        "back_label": _("⬅️ Orqaga")
    }

async def on_toggle_status(c: CallbackQuery, widget, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    actions = PostChannelActions(session)
    channel_id = manager.dialog_data.get("channel_id")
    await actions.toggle_post_channel_status(channel_id)

async def onDeleteChannel(c: CallbackQuery, widget, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    actions = PostChannelActions(session)
    channel_id = manager.dialog_data.get("channel_id")
    await actions.delete_post_channel(channel_id)
    await manager.switch_to(PostAutoPostingSG.menu)

auto_posting_dialog = Dialog(
    Window(
        Format(_("📢 <b>Auto Posting Kanallari</b>\n\nJami: {count} ta")),
        ScrollingGroup(
            Select(
                Format("{item.channel_name}"),
                id="s_channels",
                item_id_getter=lambda x: str(x.channel_id),
                items="channels",
                on_click=on_channel_click,
            ),
            id="channels_group",
            width=1,
            height=5,
        ),
        SwitchTo(Format("{add_channel_label}"), id="add_channel", state=PostAutoPostingSG.add_channel),
        Cancel(Format("{back_label}"), id="back"),
        state=PostAutoPostingSG.menu,
        getter=get_post_channels,
    ),
    Window(
        Format(_("🆔 Kanal ID raqamini yuboring yoki kanaldan xabarni forward qiling:")),
        MessageInput(on_channel_id_input),
        Back(Format(_("⬅️ Bekor qilish")), id="back"),
        state=PostAutoPostingSG.add_channel,
    ),
    Window(
        Format(_("📊 <b>Kanal ma'lumotlari:</b>\n\n nomi: {channel.channel_name}\nID: <code>{channel.channel_id}</code>\nUsername: @{channel.channel_username}\nHolati: {channel.channel_status}")),
        Button(Format("{autopost_toggle_text}"), id="toggle_status", on_click=on_toggle_status),
        Button(Format("{delete_label}"), id="delete_channel", on_click=onDeleteChannel),
        Back(Format("{back_label}"), id="back"),
        state=PostAutoPostingSG.channel_info,
        getter=get_channel_info,
    ),
)
