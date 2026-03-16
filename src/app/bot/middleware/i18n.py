from typing import Any, Dict, Optional
from aiogram.types import TelegramObject, User
from aiogram.utils.i18n import I18nMiddleware
from src.app.bot.common.i18n import i18n
from src.app.database.core import Database
from src.app.database.queries.user import UserActions

class CustomI18nMiddleware(I18nMiddleware):
    def __init__(self, db_session_factory):
        super().__init__(i18n=i18n)
        self.db_session_factory = db_session_factory

    async def get_locale(self, event: TelegramObject, data: Dict[str, Any]) -> str:
        # 1. Try to get user from data (if populated by outer middleware)
        user: Optional[User] = data.get("event_from_user")
        if not user and getattr(event, "from_user", None):
            user = event.from_user
        
        # 2. If user exists, check DB for language preference
        if user:
            async with self.db_session_factory() as session:
                user_actions = UserActions(session)
                db_user = await user_actions.get_user(user.id)
                if db_user and db_user.language_code:
                    return db_user.language_code
        
        # 3. Fallback to Telegram language code or default
        if user and user.language_code:
            return user.language_code
            
        return self.i18n.default_locale
