from aiogram.enums import ContentType
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, SwitchTo, Start, Row, Select, Group, Cancel
from aiogram_dialog.widgets.text import Const, Format, Case

from src.app.bot.dialog.getters import (
    get_op_menu_data,
    get_channel_info_data,
    get_add_channel_data,
    get_add_bot_data,
    get_bot_info_data
)
from src.app.bot.dialog.handlers import (
    handle_channel_forward,
    handle_channel_url_input,
    handle_get_channel_info,
    handle_delete_channel,
    handle_toggle_channel_op_status,
    handle_bot_username_input,
    handle_bot_url_input,
    handle_default_bot_url,
    handle_bot_name_input,
    handle_toggle_bot_op_status,
    handle_get_bot_info,
    handle_delete_bot
)
from src.app.bot.states.admin.channel import OPMenu, ChannelMenu, AddChannelState, AddBotState, BotMenu
from src.app.bot.common.i18n import lazy_gettext as _

# Главное меню управления ОП (каналы и боты)
op_management_dialog = Dialog(
    Window(
        Case(
            {
                "start_msg": Format(_("Выберите действие")),
                "not_found": Format(_("Вы еще ничего не добавили"))
            },
            selector="msg_type"
        ),
        Group(
            Button(Format(_("🗂 Каналы")), id="channels_header", when="has_channels"),
            Select(
                Format("{item.channel_name}"),
                id="channels_list",
                item_id_getter=lambda item: str(item.channel_id),
                items="channel_data",
                on_click=handle_get_channel_info,
                when="has_channels"
            ),
            width=1
        ),
        Group(
            Button(Format(_("🤖 Боты")), id="bots_header", when="has_bots"),
            Select(
                Format("{item.bot_name}"),
                id="bots_list",
                item_id_getter=lambda item: item.bot_username,
                items="bot_data",
                on_click=handle_get_bot_info,
                when="has_bots"
            ),
            width=1
        ),
        Row(
            Start(Format(_("➕ Добавить канал")), id="add_channel_btn", state=AddChannelState.get_channel_data),
            Start(Format(_("➕ Добавить бота")), id="add_bot_btn", state=AddBotState.get_bot_username),
        ),
        Cancel(Format(_("◄ Назад")), id="back_to_admin_menu"),
        state=OPMenu.menu,
        getter=get_op_menu_data
    ),
)


# Диалог добавления канала
add_channel_dialog = Dialog(
    Window(
        Case(
            {
                "start_msg": Format(
                    _("🔗 Чтобы добавить канал или группу, перешлите любой пост с канала и добавьте бота в канал.")
                ),
                "not_forwarded": Format(_("❌ Отправьте пост с канала!")),
            },
            selector="msg_type",
        ),
        MessageInput(func=handle_channel_forward, content_types=ContentType.ANY),
        Cancel(Format(_("◄ Назад")), id="back_to_op_menu"),
        state=AddChannelState.get_channel_data,
        getter=get_add_channel_data,
    ),
    Window(
        Case(
            {
                "start_msg": Format(_("🔗 Отправьте ссылку на канал")),
                "error": Format(_("❌ Произошла ошибка при добавлении канала!")),
                "already_exists": Format(_("⚠️ Канал уже существует!")),
            },
            selector="msg_type",
        ),
        MessageInput(func=handle_channel_url_input, content_types=ContentType.ANY),
        Cancel(Format(_("◄ Назад")), id="back_to_op_menu"),
        state=AddChannelState.get_channel_link,
        getter=get_add_channel_data,
    ),
)


# Диалог управления каналом
channel_management_dialog = Dialog(
    Window(
        Format("{channel_data}"),
        Group(
            Row(
                SwitchTo(Format(_("🗑 Удалить канал")), id="delete_channel_btn", state=ChannelMenu.delete_channel),
                Button(Format("{op_button}"), id="toggle_op_status_btn", on_click=handle_toggle_channel_op_status),
            ),
            Row(
                Cancel(Format(_("◄ Назад")), id="back_to_op_menu"),
            ),
        ),
        state=ChannelMenu.menu,
        getter=get_channel_info_data
    ),
    Window(
        Format(_("⚠️ Вы уверены, что хотите удалить канал?")),
        Row(
            SwitchTo(Format(_("❌ Нет")), id="cancel_delete", state=ChannelMenu.menu),
            Button(Format(_("✅ Да")), id="confirm_delete", on_click=handle_delete_channel)
        ),
        state=ChannelMenu.delete_channel
    )
)


# Диалог добавления бота
add_bot_dialog = Dialog(
    Window(
        Case(
            {
                "start_msg": Format(_("👤 Отправьте username бота (без @)")),
                "error_format": Format(_("❌ Отправьте текстовое сообщение с username бота!")),
                "already_exists": Format(_("⚠️ Бот с таким username уже существует!")),
            },
            selector="msg_type",
        ),
        MessageInput(func=handle_bot_username_input, content_types=ContentType.ANY),
        Cancel(Format(_("◄ Назад")), id="back_to_op_menu"),
        state=AddBotState.get_bot_username,
        getter=get_add_bot_data,
    ),
    Window(
        Case(
            {
                "start_msg": Format(_("🔗 Отправьте ссылку на бота")),
                "error_format": Format(_("❌ Неправильный формат ссылки!")),
            },
            selector="msg_type",
        ),
        MessageInput(func=handle_bot_url_input, content_types=ContentType.ANY),
        Button(Format(_("🔗 Использовать стандартную ссылку")), id="use_default_url", on_click=handle_default_bot_url),
        Cancel(Format(_("◄ Назад")), id="back_to_op_menu"),
        state=AddBotState.get_bot_link,
        getter=get_add_bot_data,
    ),
    Window(
        Case(
            {
                "start_msg": Format(_("📝 Отправьте отображаемое имя бота")),
                "error_format": Format(_("❌ Отправьте текстовое сообщение!")),
            },
            selector="msg_type",
        ),
        MessageInput(func=handle_bot_name_input, content_types=ContentType.ANY),
        Cancel(Format(_("◄ Назад")), id="back_to_op_menu"),
        state=AddBotState.get_bot_name,
        getter=get_add_bot_data,
    )
)


# Диалог управления ботом
bot_management_dialog = Dialog(
    Window(
        Format("{bot_data}"),
        Group(
            Row(
                SwitchTo(Format(_("🗑 Удалить бота")), id="delete_bot_btn", state=BotMenu.delete_bot),
                Button(Format("{op_button}"), id="toggle_op_status_btn", on_click=handle_toggle_bot_op_status),
            ),
            Row(
                Cancel(Format(_("◄ Назад")), id="back_to_op_menu"),
            ),
        ),
        state=BotMenu.menu,
        getter=get_bot_info_data
    ),
    Window(
        Format(_("⚠️ Вы уверены, что хотите удалить бота?")),
        Row(
            SwitchTo(Format(_("❌ Нет")), id="cancel_delete", state=BotMenu.menu),
            Button(Format(_("✅ Да")), id="confirm_delete", on_click=handle_delete_bot)
        ),
        state=BotMenu.delete_bot
    )
)