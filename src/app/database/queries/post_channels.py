from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.database.models import PostChannel

class PostChannelActions:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_post_channel(self, channel_id: int, channel_name: str, channel_username: str = None, channel_status: str = "active"):
        channel = PostChannel(
            channel_id=channel_id,
            channel_name=channel_name,
            channel_username=channel_username,
            channel_status=channel_status
        )
        self.session.add(channel)
        await self.session.commit()
        return channel

    async def get_all_post_channels(self):
        stmt = select(PostChannel)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_active_post_channels(self):
        stmt = select(PostChannel).where(PostChannel.channel_status == "active")
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_post_channel(self, channel_id: int):
        stmt = select(PostChannel).where(PostChannel.channel_id == channel_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_post_channel(self, channel_id: int):
        stmt = delete(PostChannel).where(PostChannel.channel_id == channel_id)
        await self.session.execute(stmt)
        await self.session.commit()

    async def toggle_post_channel_status(self, channel_id: int):
        channel = await self.get_post_channel(channel_id)
        if channel:
            new_status = "inactive" if channel.channel_status == "active" else "active"
            stmt = update(PostChannel).where(PostChannel.channel_id == channel_id).values(channel_status=new_status)
            await self.session.execute(stmt)
            await self.session.commit()
            return new_status
        return None
