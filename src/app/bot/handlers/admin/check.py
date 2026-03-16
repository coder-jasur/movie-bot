from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database.queries.bots import BotActions
from src.app.database.queries.channels import ChannelActions
from src.app.database.queries.user import UserActions
from src.app.bot.keyboards.inline import not_channels_button
from src.app.bot.common.i18n import i18n
_ = i18n.gettext

check_sub_router = Router()


@check_sub_router.callback_query(F.data == "check_sub")
async def check_channel_sub(
        call: CallbackQuery,  # вместо _ используем call
        dialog_manager: DialogManager,
        session: AsyncSession,
        bot: Bot,
):
    channel_actions = ChannelActions(session)
    bot_actions = BotActions(session)
    user_actions = UserActions(session)

    user_data = await user_actions.get_user(call.from_user.id)
    channel_data = await channel_actions.get_all_channels()
    bot_data = await bot_actions.get_all_bots()
    not_sub_channels = []
    not_sub_bots = []

    # Проверка подписки на обязательные каналы
    for channel in channel_data:
        # channel_status
        if channel.channel_status == "True" or channel.channel_status is True:
            try:
                user_status = await bot.get_chat_member(channel.channel_id, call.from_user.id)
                if user_status.status not in ["member", "administrator", "creator"]:
                    not_sub_channels.append(channel)
            except Exception as e:
                # Если канал не найден или возникла ошибка
                # print(f"Ошибка при проверке канала {channel.channel_id}: {e}")
                continue

    for bot_obj in bot_data:
        # bot_status
        if bot_obj.bot_status == "True" or bot_obj.bot_status is True:
            try:
               # Logic to check bot sub? Usually bots are just sending /start.
               # Original code just added to not_sub_bots list to show button?
               # The logic in original 'check_sub' for bots iterates bot_data, checks status, appends to not_sub_bots.
               # It doesn't seem to verify if user started the bot (Telegram API doesn't allow checking if user started another bot easily).
               # So maybe it just lists them?
               not_sub_bots.append(bot_obj)
            except Exception as e:
                # print(f"Ошибка при проверке канала {bot_obj.bot_username}: {e}")
                continue

    # Если пользователь подписан на все каналы
    if not not_sub_channels:
        if not user_data:
            # Добавление нового пользователя
            await user_actions.add_user(
                call.from_user.id,
                call.from_user.username or call.from_user.first_name,
            )

        name = (
                call.from_user.first_name
                or call.from_user.last_name
                or call.from_user.full_name
                or _("Do'stim")
        )

        # Приветственное сообщение
        await call.message.edit_text(
            _("""<b>👋 Salom {name}</b>

<b>Botimizga xush kelibsiz.</b>

<b>🍿 Kino kodini yuboring:</b>""").format(name=name)
        )
        # Удаление старого сообщения

    # Если есть каналы, на которые пользователь не подписан
    else:
        try:
            await call.message.edit_text(
                _("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇"),
                reply_markup=not_channels_button(not_sub_channels, not_sub_bots),
            )
        except Exception as e:
            # Если edit_text не сработал (старое сообщение)
            # print(f"Ошибка при редактировании сообщения: {e}")
            # await call.message.delete() # Might fail if message too old
            await call.message.answer(
                _("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇"),
                reply_markup=not_channels_button(not_sub_channels, not_sub_bots),
            )

    await call.answer()
