from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.database.queries.admin import AdminActions
from src.app.core.config import load_config

class IsAdmin(Filter):
    async def __call__(self, event: Message | CallbackQuery, session: AsyncSession) -> bool:
        settings = load_config()
        # Root admin support from .env
        if event.from_user.id in settings.admins_ids:
            return True
            
        actions = AdminActions(session)
        return await actions.is_admin(event.from_user.id)

class IsSuperAdmin(Filter):
    async def __call__(self, event: Message | CallbackQuery, session: AsyncSession) -> bool:
        settings = load_config()
        # Root admin support from .env
        if event.from_user.id in settings.admins_ids:
            return True
            
        actions = AdminActions(session)
        level = await actions.get_admin_level(event.from_user.id)
        return level >= 2
