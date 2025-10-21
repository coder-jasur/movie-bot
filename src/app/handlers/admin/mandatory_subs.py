import asyncpg
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager

from src.app.database.queries.bots import BotActions
from src.app.database.queries.channels import ChannelActions
from src.app.keyboards.callback_data import ChannelsCD, BotCD
from src.app.states.admin.channel import ChannelsMenu

mandatory_subs_router = Router()

@mandatory_subs_router.callback_query(F.data == "mandatory_subscriptions")
async def send_admin_menu(callback: CallbackQuery, dialog_manager: DialogManager):
    await dialog_manager.start(ChannelsMenu.menu)


@mandatory_subs_router.callback_query(ChannelsCD.filter())
async def channel_set_up_menu(call: CallbackQuery, pool: asyncpg.Pool, callback_data: ChannelsCD):
    channel_actions = ChannelActions(pool)
    channel_data = channel_actions.get_channel(callback_data.channel_id)
    if callback_data.actions == "set_up_menu":
        await call.message.answer(
            f"🆔 ID: {channel_data[0]}\n"
            f"📛 Название: {channel_data[1]}"
            f"🔗 Юзернейм: {channel_data[2]}\n"
            f"📶 Статус: {channel_data[3]}\n"
            f"🚀 Ссылка: {channel_data[5]}"
        )

@mandatory_subs_router.callback_query(BotCD.filter())
async def bot_set_up_menu(call: CallbackQuery, pool: asyncpg.Pool, callback_data: BotCD):
    bot_actions = BotActions(pool)



