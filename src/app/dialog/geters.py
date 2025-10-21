import asyncpg
from aiogram_dialog import DialogManager

from src.app.database.queries.channels import ChannelActions


async def op_menu_getter(dialog_manager: DialogManager, **_):
    pool: asyncpg.pool = dialog_manager.middleware_data["pool"]


    channel_actions = ChannelActions(pool)
    channel_data = await channel_actions.get_all_channels()

    message_type = ""

    if not channel_data:
        message_type = "not_found"

    return {
        "channel_data": channel_data,
        "msg_type": message_type if message_type else "start_msg"
    }

async def add_chanenl_getter(dialog_manager: DialogManager, **_):
    return {
        "msg_type": dialog_manager.dialog_data.get("msg_type", "start_msg")
    }


async def channel_info_getter(dialog_manager: DialogManager, **_):
    channel_id = dialog_manager.start_data.get("channel_id")
    dialog_manager.dialog_data["channel_id"] = channel_id

    pool: asyncpg.Pool = dialog_manager.middleware_data["pool"]

    channel_actions = ChannelActions(pool)

    channel_data = await channel_actions.get_channel(channel_id)

    if channel_data[3] == "True":
        op_button = "🚫 Убрать из ОП"
    else:
        op_button = "➕ добавить в ОП"

    return {
        "channel_data": (
            "📢 Полная информация о канале\n\n"
            f"🆔 ID: <code>{channel_data[0]}</code>\n"
            f"📛 Название: <b>{channel_data[1]}</b>\n"
            f"🔗 Юзернейм: <b>@{channel_data[2]}</b>\n"
            f"📶 Статус: <code>{channel_data[3]}</code>\n"
            f"🚀 Ссылка: {channel_data[5]}\n\n"
        ),
        "op_button": op_button
    }
