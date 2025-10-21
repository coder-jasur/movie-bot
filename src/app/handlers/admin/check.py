import asyncpg
from aiogram import Router, F, Bot
from aiogram_dialog import DialogManager

from src.app.database.queries.channels import ChannelActions
from src.app.database.queries.user import UserActions
from src.app.keyboards.inline import not_channels_button, start_menu

check_sub_router = Router()

@check_sub_router.callback_query(F.data == "check_sub")
async def check_channel_sub(
    _,
    dialog_manager: DialogManager,
    pool: asyncpg.Pool,
    bot: Bot,
):
    channel_actions = ChannelActions(pool)
    user_actions = UserActions(pool)
    user_data = await user_actions.get_user(dialog_manager.event.from_user.id)
    channel_data = await channel_actions.get_all_channels()
    not_sub_channels = []

    for channel in channel_data:
        if channel[3] == "True":
            user_status = await bot.get_chat_member(channel[0], dialog_manager.event.from_user.id)
            if user_status.status not in ["member", "administrator", "creator"]:
                not_sub_channels.append(channel)

    if not not_sub_channels:
        if not user_data:
            await user_actions.add_user(
                dialog_manager.event.from_user.id,
                dialog_manager.event.from_user.username or dialog_manager.event.from_user.first_name,
            )
        else:
            await dialog_manager.event.message.answer(
                f"👋 Assalomu aleykum {dialog_manager.event.from_user.first_name}\n\n"
                "👀 Film - Serila - Multfilm ko'rish uchun:\n\n"
                "1️⃣ Kanalga obuna bo'ling\n"
                "2⃣  Instagram yoki telegram kanalimizdan kerakli filmni tanlang👇\n"
                "3⃣  Botga film kodini yuboring✍️\n\n"
                "🎬 Eng so'nggi filmlar va seriallar! Faqat siz uchun! 🍿",
                reply_markup=start_menu
            )
    elif not_sub_channels:
        await dialog_manager.event.message.answer(
            "Botdan foydalanish uchun ushbu kanallarga obuna bo'ling",
            reply_markup=not_channels_button(not_sub_channels)
        )
    else:
        try:
            await dialog_manager.event.message.edit_text(
                "Botdan foydalanish uchun ushbu kanallarga obuna bo'ling",
                reply_markup=not_channels_button(channel_data),
            )

        except Exception as e:
            print(e)
            await dialog_manager.event.message.edit_text(
                "Botdan foydalanish uchun ushbu kanallarga obuna bo'ling" + ".",
                reply_markup=not_channels_button(channel_data),
            )
