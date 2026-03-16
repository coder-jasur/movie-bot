from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from aiogram_dialog import DialogManager

from src.app.database.queries.bots import BotActions
from src.app.database.queries.channels import ChannelActions


# ==================== OP MENU GETTERS ====================

async def get_op_menu_data(dialog_manager: DialogManager, **_) -> Dict[str, Any]:
    """
    Получает данные для главного меню ОП (список каналов и ботов).

    Returns:
        Dict с данными каналов, ботов и типом сообщения
    """
    session: AsyncSession = dialog_manager.middleware_data["session"]

    # Получаем все каналы
    channel_actions = ChannelActions(session)
    channels = await channel_actions.get_all_channels()

    # Получаем всех ботов
    bot_actions = BotActions(session)
    bots = await bot_actions.get_all_bots()

    # Определяем тип сообщения
    msg_type = "not_found" if not channels and not bots else "start_msg"

    return {
        "channel_data": channels or [],
        "bot_data": bots or [],
        "msg_type": msg_type,
        "has_channels": bool(channels),
        "has_bots": bool(bots)
    }


# ==================== CHANNEL GETTERS ====================

async def get_add_channel_data(dialog_manager: DialogManager, **_) -> Dict[str, str]:
    """
    Получает данные для окна добавления канала.

    Returns:
        Dict с типом сообщения
    """
    return {
        "msg_type": dialog_manager.dialog_data.get("msg_type", "start_msg")
    }


async def get_channel_info_data(dialog_manager: DialogManager, **_) -> Dict[str, str]:
    """
    Получает полную информацию о канале для отображения.

    Returns:
        Dict с данными канала и текстом кнопки ОП
    """
    # Получаем ID канала из стартовых данных
    channel_id = dialog_manager.start_data.get("channel_id")
    dialog_manager.dialog_data["channel_id"] = channel_id

    session: AsyncSession = dialog_manager.middleware_data["session"]
    channel_actions = ChannelActions(session)

    # Получаем данные канала из БД
    channel_data = await channel_actions.get_channel(channel_id)

    if not channel_data:
        return {
            "channel_data": "❌ Канал не найден",
            "op_button": "—"
        }

    # Определяем текст кнопки в зависимости от статуса
    is_in_op = channel_data.channel_status == "True"
    op_button = "🚫 Убрать из ОП" if is_in_op else "➕ Добавить в ОП"

    # Форматируем данные для отображения
    channel_info = (
        "📢 <b>Полная информация о канале</b>\n\n"
        f"🆔 <b>ID:</b> <code>{channel_data.channel_id}</code>\n"
        f"📛 <b>Название:</b> {channel_data.channel_name}\n"
        f"🔗 <b>Username:</b> @{channel_data.channel_username or 'не указан'}\n"
        f"📶 <b>Статус в ОП:</b> {'✅ Активен' if is_in_op else '❌ Неактивен'}\n"
        f"🔗 <b>Ссылка:</b> {channel_data.channel_url}\n"
    )

    return {
        "channel_data": channel_info,
        "op_button": op_button
    }


# ==================== BOT GETTERS ====================

async def get_add_bot_data(dialog_manager: DialogManager, **_) -> Dict[str, str]:
    """
    Получает данные для окна добавления бота.

    Returns:
        Dict с типом сообщения
    """
    return {
        "msg_type": dialog_manager.dialog_data.get("msg_type", "start_msg")
    }


async def get_bot_info_data(dialog_manager: DialogManager, **_) -> Dict[str, str]:
    """
    Получает полную информацию о боте для отображения.

    Returns:
        Dict с данными бота и текстом кнопки ОП
    """
    # Получаем username бота из стартовых данных
    bot_username = dialog_manager.start_data.get("bot_username")
    dialog_manager.dialog_data["bot_username"] = bot_username

    session: AsyncSession = dialog_manager.middleware_data["session"]
    bot_actions = BotActions(session)

    # Получаем данные бота из БД
    bot_data = await bot_actions.get_bot(bot_username)

    if not bot_data:
        return {
            "bot_data": "❌ Бот не найден",
            "op_button": "—"
        }

    # Определяем текст кнопки в зависимости от статуса
    is_in_op = bot_data.bot_status == "True"
    op_button = "🚫 Убрать из ОП" if is_in_op else "➕ Добавить в ОП"

    # Форматируем данные для отображения
    bot_info = (
        "🤖 <b>Полная информация о боте</b>\n\n"
        f"📛 <b>Название:</b> {bot_data.bot_name}\n"
        f"🔗 <b>Username:</b> @{bot_data.bot_username}\n"
        f"📶 <b>Статус в ОП:</b> {'✅ Активен' if is_in_op else '❌ Неактивен'}\n"
        f"🔗 <b>Ссылка:</b> {bot_data.bot_url}\n"
    )

    return {
        "bot_data": bot_info,
        "op_button": op_button
    }