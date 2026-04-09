import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database.queries.user import UserActions
from src.app.bot.handlers.user.account import get_tashkent_time

logger = logging.getLogger(__name__)

class VIPExpiryMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Only check for messages and callbacks
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        session: AsyncSession = data.get("session")
        if not session:
            return await handler(event, data)

        user_id = event.from_user.id
        user_actions = UserActions(session)
        user = await user_actions.get_user(user_id)

        if user and user.vip_status == "active" and user.vip_expires_at:
            now = get_tashkent_time()
            if user.vip_expires_at < now:
                # VIP expired, update status to None (consistent with account.py)
                await user_actions.update_user(
                    tg_id=user_id,
                    vip_status=None # Clear status
                )
                logger.info(f"VIP status expired and cleared for user {user_id}")
                
                # We update the user object in data if it exists so downstream handlers see it
                if "user" in data:
                    data["user"].vip_status = None

        return await handler(event, data)
