from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.enums import ChatType
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database.queries.channels import ChannelActions
from src.app.database.queries.admin import AdminActions
from src.app.bot.keyboards.callback_data import LanguageCD
from src.app.core.config import Settings


class CheckSubscription(BaseFilter):
    _channels_cache = []
    _last_update = None
    _cache_ttl = timedelta(minutes=5)

    async def __call__(self, event: Message | CallbackQuery, session: AsyncSession, bot: Bot, **kwargs):
        # Only check subscription in private chats
        if isinstance(event, Message):
            if event.chat.type != ChatType.PRIVATE:
                return False
            # Ignore /start command
            if event.text and event.text.startswith("/start"):
                return False
        elif isinstance(event, CallbackQuery):
            if event.message.chat.type != ChatType.PRIVATE:
                return False
            # Ignore language selection callbacks
            if event.data and (event.data.startswith("lang:") or event.data == "close"):
                return False

        # Admin bypass
        settings: Settings = kwargs.get("settings")
        if settings and event.from_user.id in settings.admins_ids:
            return False
        
        # Database Admin bypass
        admin_actions = AdminActions(session)
        if await admin_actions.is_admin(event.from_user.id):
            return False
        
        # Ignore /language command
        if isinstance(event, Message) and event.text and event.text.startswith("/language"):
            return False

        # Ignore VIP users
        from src.app.database.queries.user import UserActions
        user = await UserActions(session).get_user(event.from_user.id)
        if user and user.vip_status == "active":
            return False

        # Cache logic to prevent DB spam on every message
        now = datetime.now()
        if not self._last_update or (now - self._last_update) > self._cache_ttl:
            channel_actions = ChannelActions(session)
            self._channels_cache = await channel_actions.get_all_channels()
            self._last_update = now
        
        channel_data = self._channels_cache

        if not channel_data:
            return False

        for channel in channel_data:
            # Check for string "True" or boolean True just in case
            if channel.channel_status == "True" or channel.channel_status is True:
                try:
                    user_status = await bot.get_chat_member(channel.channel_id, event.from_user.id)
                    if user_status.status not in ["member", "administrator", "creator"]:
                        return True
                except Exception:
                    # Ignore errors, maybe channel not found or bot kicked
                    continue
        return False
