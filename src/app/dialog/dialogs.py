from operator import itemgetter

from aiogram.enums import ContentType
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, SwitchTo, Start, Row, Select, Group
from aiogram_dialog.widgets.text import Const, Format, Case

from src.app.dialog.geters import op_menu_getter, channel_info_getter, add_chanenl_getter
from src.app.dialog.handlers import (
    add_channel_input, get_channel_info, on_delete_channel,
    on_edit_op, take_channel_data, on_done_dialog
)
from src.app.states.admin.channel import ChannelsMenu, ChannelMenu, AddChannelSG

op_dialog = Dialog(
    Window(
        Case(
            {
                "start_msg": Format("Выберите действие"),
                "not_found": Format("вы еще ничего не добавили")
            },
            selector="msg_type"
        ),
        Group(
            Select(
                Format("{item[1]}"),
                id="channels_buttons",
                item_id_getter=itemgetter(0),
                items="channel_data",
                on_click=get_channel_info,
            ),
            width=1
        ),
        Start(Const("добавить канал"), id="add_channel", state=AddChannelSG.get_channel_data),
        Button(Const("◄ назад"), id="back_to_admin_menu", on_click=on_done_dialog),
        state=ChannelsMenu.menu,
        getter=op_menu_getter
    ),
)

add_channel_dialog = Dialog(
    Window(
        Case(
            {
                "start_msg": Const(
                    "🔗 Чтобы добавить канал или группу, отправьте любой пост с канала и добавьте бота в канал или группу."
                ),
                "not_forwarded": Const("отправьте пост с канала!"),
            },
            selector="msg_type",
        ),
        MessageInput(func=take_channel_data, content_types=ContentType.ANY),
        Start(Const("◄ назад"), id="op_menu", state=ChannelsMenu.menu),
        state=AddChannelSG.get_channel_data,
        getter=add_chanenl_getter,
    ),
    Window(
        Case(
            {
                "start_msg": Const("оптправьте ссылку на канал"),
                "error": Const("Произошла ошибка при добавлении канала!"),
                "already_exists": Const("✖ Канал уже существует!"),
            },
            selector="msg_type",
        ),
        MessageInput(func=add_channel_input, content_types=ContentType.ANY),
        Start(Const("◄ назад"), id="op_menu", state=ChannelsMenu.menu),
        state=AddChannelSG.get_channel_link,
        getter=add_chanenl_getter,
    ),
)

channel_menu_dialog = Dialog(
    Window(
        Format("{channel_data}"),
        Group(
            Row(
                SwitchTo(Const("✖ Удалить канал"), id="delete_channel", state=ChannelMenu.delite_channel),
                Button(Format("{op_button}"), id="remove_from_op", on_click=on_edit_op),
            ),
            Row(
                Start(Const("◄ Назад"), id="back", state=ChannelsMenu.menu),
            ),
        ),
        state=ChannelMenu.menu,
        getter=channel_info_getter
    ),
    Window(
        Const("Вы уверены, что хотите удалить канал?"),
        Row(
            Start(Const("Нет"), id="back", state=ChannelMenu.menu),
            Button(Const("Да"), id="delete", on_click=on_delete_channel)
        ),
        state=ChannelMenu.delite_channel
    )
)
