import logging
from typing import Any

import asyncpg
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

from src.app.keyboards.inline import admin_menu
from src.app.services.broadcaster import Broadcaster
from src.app.states.admin.admin import BroadcastingManagerSG

logger = logging.getLogger(__name__)

broadcater_router = Router()

@broadcater_router.callback_query(F.data == "broadcast")
async def start_broadcasting_manager(call: CallbackQuery, state: FSMContext):
    await call.message.answer(
        "Отправьте <b>сообщение</b> для рассылки.",
        parse_mode="HTML"
    )
    await state.set_state(BroadcastingManagerSG.get_message)


@broadcater_router.message(BroadcastingManagerSG.get_message)
async def get_broadcasting_message(message: Message, state: FSMContext, **kwargs):
    if message.poll:
        await message.delete()
        return await message.answer(
            "❌ Неправильный формат!"
        )

    album = kwargs.get("album")
    if album:
        await state.update_data(album=album)
    else:
        await state.update_data(message=message)

    await state.set_state(BroadcastingManagerSG.confirm_broadcasting)
    await message.answer(
        "Вы уверены что хотите начать рассылку",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Отменить", callback_data="broadcast:cancel"),
                    InlineKeyboardButton(text="Подтвердить", callback_data="broadcast:confirm"),
                ]
            ]
        )
    )


@broadcater_router.callback_query(BroadcastingManagerSG.confirm_broadcasting, F.data == "broadcast:cancel")
async def on_cancel_broadcast(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(
        text="выберите действия",
        reply_markup=admin_menu
    )


@broadcater_router.callback_query(BroadcastingManagerSG.confirm_broadcasting, F.data == "broadcast:confirm")
async def on_confirm_broadcast(call: CallbackQuery, state: FSMContext, pool: asyncpg.Pool, bot: Bot) -> Any:
    try:
        data = await state.get_data()
        print(data)
        message = data.get("message")
        album = data.get("album")

        if not album and not message:
            raise ValueError("Broadcasting message not present!")

        await call.message.edit_text("Начинаем рассылку пользователям...")
        broadcaster = Broadcaster(
            bot=bot,
            pool=pool,
            admin_id=call.from_user.id,
            broadcasting_message=message,
            album=album,
            batch_size=5000  # Устанавливаем размер пачки
        )

        # Запуск рассылки
        count_blocked, count_deleted, count_limited, count_deactivated = await broadcaster.broadcast()

        # Вывод результатов рассылки
        result_message = "Рассылка завершена."

        if count_blocked:
            result_message += (
                f"\nОбнаружено {count_blocked} заблокировавших бота."
            )

        if count_deleted:
            result_message += (
                f"\nОбнаружено {count_deleted} аккаунтов, которые были удалены."
            )

        if count_limited:
            result_message += (
                f"\nОбнаружено {count_limited} аккаунтов, которые ограничены тг."
            )

        if count_deactivated:
            result_message += (
                f"\nОбнаружено {count_deleted} аккаунтов, которые деактивированы."
            )

        if not count_blocked and not count_deleted and not count_limited and not count_deactivated:
            result_message += "\nВсе сообщения доставлены успешно."

        await call.message.edit_text(result_message)

    except ValueError as e:
        # Обработка ошибок валидации в Broadcaster
        return await call.message.answer(f"Ошибка конфигурации рассылки: {e}")

    except Exception as e:
        logger.error(f"Ошибка при выполнении рассылки: {e}")
        return await call.message.answer(f"Ошибка при выполнении рассылки: {e}")
