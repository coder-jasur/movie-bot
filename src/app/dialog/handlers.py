import logging

import asyncpg
from aiogram.types import (
    CallbackQuery, Message,
)
from aiogram_dialog import DialogManager

from src.app.database.queries.channels import ChannelActions
from src.app.keyboards.inline import admin_menu
from src.app.states.admin.channel import ChannelsMenu, ChannelMenu, AddChannelSG

logger = logging.getLogger(__name__)


async def take_channel_data(message: Message, _, dialog_manager: DialogManager) -> None:
    pool: asyncpg.Pool = dialog_manager.middleware_data["pool"]

    if message.forward_from_chat:
        channel_actions = ChannelActions(pool)
        channel_data = await channel_actions.get_channel(message.forward_from_chat.id)

        if channel_data:
            dialog_manager.dialog_data["msg_type"] = "already_exists"
            await dialog_manager.switch_to(AddChannelSG.get_channel_link)
            return

        channel_data = {
            "channel_name": message.forward_from_chat.full_name,
            "channel_id": message.forward_from_chat.id,
            "channel_username": message.forward_from_chat.username
        }
        dialog_manager.dialog_data["channel_data"] = channel_data

        await dialog_manager.switch_to(AddChannelSG.get_channel_link)
    else:
        dialog_manager.dialog_data["msg_type"] = "not_forwarded"
        return


async def add_channel_input(message: Message, _, dialog_manager: DialogManager):
    pool: asyncpg.Pool = dialog_manager.middleware_data["pool"]
    channel_actions = ChannelActions(pool)
    channel_data = dialog_manager.dialog_data.get("channel_data")
    print(message.text)

    try:
        await channel_actions.add_channel(
            channel_id=channel_data["channel_id"],
            channel_name=channel_data["channel_name"],
            channel_username=channel_data["channel_username"],
            channel_url=message.text
        )

    except Exception as e:
        print("Add channel error:", e)
        dialog_manager.dialog_data["msg_type"] = "error"
        return
    finally:
        await dialog_manager.done()
        await dialog_manager.start(ChannelsMenu.menu)


async def get_channel_info(_, __, dialog_manager: DialogManager, item_id: str):
    await dialog_manager.start(ChannelMenu.menu, data={"channel_id": int(item_id)})


async def add_channel(_, __, dialog_manager: DialogManager):
    await dialog_manager.start(ChannelMenu.menu)


async def on_delete_channel(_, __, manager: DialogManager):
    pool: asyncpg.Pool = manager.middleware_data["pool"]
    channel_id = manager.dialog_data.get("channel_id")
    channel_actions = ChannelActions(pool)
    print(channel_id)

    await channel_actions.delete_channel(channel_id)
    await manager.start(ChannelsMenu.menu)


async def on_edit_op(_, __, manager: DialogManager):
    pool: asyncpg.Pool = manager.middleware_data["pool"]
    channel_id = manager.dialog_data.get("channel_id")
    channel_actions = ChannelActions(pool)
    channel_data = await channel_actions.get_channel(channel_id)

    if channel_data[3] == "True":
        await channel_actions.update_channel_status("False", channel_id)
    elif channel_data[3] == "False":
        await channel_actions.update_channel_status("True", channel_id)
    await manager.switch_to(ChannelMenu.menu)


async def on_done_dialog(call: CallbackQuery, _, dialog_manaegr: DialogManager):
    await dialog_manaegr.done()
    await call.message.edit_text(
        text="выберите действия",
        reply_markup=admin_menu
    )
