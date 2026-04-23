from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from aiogram_dialog import DialogManager

from src.app.bot.common.i18n import lazy_gettext as gettext_
from src.app.database.queries.bots import BotActions
from src.app.database.queries.channels import ChannelActions
from src.app.database.queries.urls import UrlActions


# ==================== OP MENU GETTERS ====================

async def get_op_menu_data(dialog_manager: DialogManager, **kwargs) -> Dict[str, Any]:
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

    # Получаем все URL
    url_actions = UrlActions(session)
    urls = await url_actions.get_all_urls()

    # Определяем тип сообщения
    msg_type = "not_found" if not channels and not bots and not urls else "start_msg"

    return {
        "channel_data": channels or [],
        "bot_data": bots or [],
        "url_data": urls or [],
        "msg_type": msg_type,
        "has_channels": bool(channels),
        "has_bots": bool(bots),
        "has_urls": bool(urls)
    }


# ==================== CHANNEL GETTERS ====================

async def get_add_channel_data(dialog_manager: DialogManager, **kwargs) -> Dict[str, str]:
    """
    Получает данные для окна добавления канала.

    Returns:
        Dict с типом сообщения
    """
    return {
        "msg_type": dialog_manager.dialog_data.get("msg_type", "start_msg")
    }


async def get_channel_info_data(dialog_manager: DialogManager, **kwargs) -> Dict[str, str]:
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
            "channel_data": gettext_("❌ Канал не найден"),
            "op_button": "—"
        }

    # Определяем текст кнопки в зависимости от статуса
    is_in_op = channel_data.channel_status == "True"
    op_button = gettext_("🚫 Убрать из ОП") if is_in_op else gettext_("➕ Добавить в ОП")

    # Форматируем данные для отображения
    channel_info = (
        f"📢 <b>{gettext_('Полная информация о канале')}</b>\n\n"
        f"🆔 <b>{gettext_('ID:')}</b> <code>{channel_data.channel_id}</code>\n"
        f"📛 <b>{gettext_('Название:')}</b> {channel_data.channel_name}\n"
        f"🔗 <b>{gettext_('Username:')}</b> @{channel_data.channel_username or gettext_('не указан')}\n"
        f"📶 <b>{gettext_('Статус в ОП:')}</b> {'✅ ' + gettext_('Активен') if is_in_op else '❌ ' + gettext_('Неактивен')}\n"
        f"🔗 <b>{gettext_('Ссылка:')}</b> {channel_data.channel_url}\n"
    )

    return {
        "channel_data": channel_info,
        "op_button": op_button
    }


# ==================== BOT GETTERS ====================

async def get_add_bot_data(dialog_manager: DialogManager, **kwargs) -> Dict[str, str]:
    """
    Получает данные для окна добавления бота.

    Returns:
        Dict с типом сообщения
    """
    return {
        "msg_type": dialog_manager.dialog_data.get("msg_type", "start_msg")
    }


async def get_bot_info_data(dialog_manager: DialogManager, **kwargs) -> Dict[str, str]:
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
            "bot_data": gettext_("❌ Бот не найден"),
            "op_button": "—"
        }

    # Определяем текст кнопки в зависимости от статуса
    is_in_op = bot_data.bot_status == "True"
    op_button = gettext_("🚫 Убрать из ОП") if is_in_op else gettext_("➕ Добавить в ОП")

    # Форматируем данные для отображения
    bot_info = (
        f"🤖 <b>{gettext_('Полная информация о боте')}</b>\n\n"
        f"📛 <b>{gettext_('Название:')}</b> {bot_data.bot_name}\n"
        f"🔗 <b>{gettext_('Username:')}</b> @{bot_data.bot_username}\n"
        f"📶 <b>{gettext_('Статус в ОП:')}</b> {'✅ ' + gettext_('Активен') if is_in_op else '❌ ' + gettext_('Неактивен')}\n"
        f"🔗 <b>{gettext_('Ссылка:')}</b> {bot_data.bot_url}\n"
    )

    return {
        "bot_data": bot_info,
        "op_button": op_button
    }


# ==================== URL GETTERS ====================

async def get_add_url_data(dialog_manager: DialogManager, **kwargs) -> Dict[str, str]:
    return {
        "msg_type": dialog_manager.dialog_data.get("msg_type", "start_msg")
    }


async def get_url_info_data(dialog_manager: DialogManager, **kwargs) -> Dict[str, str]:
    url_id = dialog_manager.start_data.get("url_id")
    dialog_manager.dialog_data["url_id"] = url_id

    session: AsyncSession = dialog_manager.middleware_data["session"]
    url_actions = UrlActions(session)

    url_data = await url_actions.get_url(int(url_id))

    if not url_data:
        return {
            "url_data": gettext_("❌ URL не найден"),
            "op_button": "—"
        }

    is_in_op = url_data.url_status == "True"
    op_button = gettext_("🚫 Убрать из ОП") if is_in_op else gettext_("➕ Добавить в ОП")

    url_info = (
        f"🌐 <b>{gettext_('Полная информация об URL')}</b>\n\n"
        f"📛 <b>{gettext_('Название:')}</b> {url_data.url_name}\n"
        f"📶 <b>{gettext_('Статус в ОП:')}</b> {'✅ ' + gettext_('Активен') if is_in_op else '❌ ' + gettext_('Неактивен')}\n"
        f"🔗 <b>{gettext_('Ссылка:')}</b> {url_data.url_link}\n"
    )

    return {
        "url_data": url_info,
        "op_button": op_button
    }
