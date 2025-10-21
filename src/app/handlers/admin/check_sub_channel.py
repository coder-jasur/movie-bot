import asyncpg
from aiogram import Router, Bot
from aiogram.types import Message, CallbackQuery

from src.app.database.queries.channels import ChannelActions
from src.app.filters.check_channel_sub import CheckSubscription
from src.app.keyboards.inline import not_channels_button

check_channel_sub_router = Router()
check_channel_sub_router.message.filter(CheckSubscription())
check_channel_sub_router.callback_query.filter(CheckSubscription())


@check_channel_sub_router.message()
async def check_channel_sub_message(message: Message, pool: asyncpg.Pool, bot: Bot):
    channel_actions = ChannelActions(pool)
    channel_data = await channel_actions.get_all_channels()
    not_sub_channels = []
    for channel in channel_data:
        if channel[3] == "True":
            user_status = await bot.get_chat_member(channel[0], message.from_user.id)
            if user_status.status not in ["member", "administrator", "creator"]:
                not_sub_channels.append(channel)


    await message.answer(
        "Botdan foydalanish uchun ushbu kanallarga obuna bo'ling",
        reply_markup=not_channels_button(not_sub_channels)
    )





@check_channel_sub_router.callback_query()
async def check_channel_sub_call(call: CallbackQuery, pool: asyncpg.Pool, bot: Bot):
    channel_actions = ChannelActions(pool)
    channel_data = await channel_actions.get_all_channels()
    not_sub_channels = []
    for channel in channel_data:
        if channel[3] == "True":
            user_status = await bot.get_chat_member(channel[0], call.from_user.id)
            if user_status.status not in ["member", "administrator", "creator"]:
                not_sub_channels.append(channel)

    print(not_sub_channels)

    await call.message.answer(
        "Botdan foydalanish uchun ushbu kanallarga obuna bo'ling",
        reply_markup=not_channels_button(not_sub_channels)
    )
