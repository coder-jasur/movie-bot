from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database.queries.user import UserActions
from src.app.bot.handlers.user.account import get_tashkent_time

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
                # VIP expired, update status
                await user_actions.update_user(
                    tg_id=user_id,
                    vip_status="expired"
                )
                # We don't notify here to avoid spamming on every event, 
                # but the profile will show "expired".

        return await handler(event, data)
