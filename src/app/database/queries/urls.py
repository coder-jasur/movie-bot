from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database.models import SubUrl


class UrlActions:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_url(
            self,
            url_name: str,
            url_link: str,
            url_status: str = "True"
    ):
        url = SubUrl(
            url_name=url_name,
            url_link=url_link,
            url_status=url_status
        )
        self.session.add(url)
        await self.session.commit()

    async def get_url(self, url_id: int):
        stmt = select(SubUrl).where(SubUrl.url_id == url_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_urls(self):
        stmt = select(SubUrl)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_url_status(self, new_url_status: str, url_id: int):
        stmt = update(SubUrl).where(SubUrl.url_id == url_id).values(url_status=new_url_status)
        await self.session.execute(stmt)
        await self.session.commit()

    async def delete_url(self, url_id: int):
        stmt = delete(SubUrl).where(SubUrl.url_id == url_id)
        await self.session.execute(stmt)
        await self.session.commit()
