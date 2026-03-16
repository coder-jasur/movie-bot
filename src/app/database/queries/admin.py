from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.database.models import Admin, User

class AdminActions:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_admin(self, tg_id: int, username: str = None, level: int = 1):
        # Check if already exists
        existing = await self.get_admin(tg_id)
        if existing:
            await self.update_admin(tg_id, level=level, is_active=True)
            return existing
            
        admin = Admin(
            tg_id=tg_id,
            username=username,
            level=level
        )
        self.session.add(admin)
        await self.session.commit()
        return admin

    async def get_admin(self, tg_id: int):
        stmt = select(Admin).where(Admin.tg_id == tg_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_admins(self):
        stmt = select(Admin).order_by(Admin.level.desc(), Admin.created_at.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_admin(self, tg_id: int, **kwargs):
        stmt = update(Admin).where(Admin.tg_id == tg_id).values(**kwargs)
        await self.session.execute(stmt)
        await self.session.commit()

    async def delete_admin(self, tg_id: int):
        stmt = delete(Admin).where(Admin.tg_id == tg_id)
        await self.session.execute(stmt)
        await self.session.commit()

    async def is_admin(self, tg_id: int) -> bool:
        admin = await self.get_admin(tg_id)
        return admin is not None and admin.is_active

    async def get_admin_level(self, tg_id: int) -> int:
        admin = await self.get_admin(tg_id)
        if admin and admin.is_active:
            return admin.level
        return 0

    async def find_user_by_username_or_id(self, query: str):
        """Finds a user from the 'users' table to help adding an admin."""
        if query.isdigit():
            stmt = select(User).where(User.tg_id == int(query))
        else:
            username = query[1:] if query.startswith("@") else query
            stmt = select(User).where(User.username == username)
            
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
