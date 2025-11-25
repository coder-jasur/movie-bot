import asyncpg
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager

from src.app.database.queries.channels import ChannelActions
from src.app.database.queries.user import UserActions
from src.app.keyboards.inline import not_channels_button, start_menu

check_sub_router = Router()


@check_sub_router.callback_query(F.data == "check_sub")
async def check_channel_sub(
        call: CallbackQuery,  # вместо _ используем call
        dialog_manager: DialogManager,
        pool: asyncpg.Pool,
        bot: Bot,
):
    channel_actions = ChannelActions(pool)
    user_actions = UserActions(pool)
    user_data = await user_actions.get_user(call.from_user.id)
    channel_data = await channel_actions.get_all_channels()
    not_sub_channels = []

    # Проверка подписки на обязательные каналы
    for channel in channel_data:
        # channel[3] должен быть boolean True, а не строкой "True"
        if channel[3] is True or channel[3] == "True":
            try:
                user_status = await bot.get_chat_member(channel[0], call.from_user.id)
                if user_status.status not in ["member", "administrator", "creator"]:
                    not_sub_channels.append(channel)
            except Exception as e:
                # Если канал не найден или возникла ошибка
                print(f"Ошибка при проверке канала {channel[0]}: {e}")
                continue

    # Если пользователь подписан на все каналы
    if not not_sub_channels:
        if not user_data:
            # Добавление нового пользователя
            await user_actions.add_user(
                call.from_user.id,
                call.from_user.username or call.from_user.first_name,
            )

        # Приветственное сообщение
        await call.message.answer(
            f"👋 <b>Привет, {call.from_user.first_name or call.from_user.full_name}</b>\n\n"
            f"<b>Добро пожаловать в наш бот.</b>\n\n"
            f"<b>🍿 Отправьте код фильма: </b>",
            parse_mode="HTML"
        )
        # Удаление старого сообщения
        try:
            await call.message.delete()
        except:
            pass

    # Если есть каналы, на которые пользователь не подписан
    else:
        try:
            await call.message.edit_text(
                "Чтобы пользоваться ботом, подпишитесь на следующие каналы 👇",
                reply_markup=not_channels_button(not_sub_channels),
            )
        except Exception as e:
            # Если edit_text не сработал (старое сообщение)
            print(f"Ошибка при редактировании сообщения: {e}")
            await call.message.answer(
                "Чтобы пользоваться ботом, подпишитесь на следующие каналы 👇",
                reply_markup=not_channels_button(not_sub_channels),
            )

    await call.answer()
