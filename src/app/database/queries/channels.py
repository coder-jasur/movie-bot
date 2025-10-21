import asyncpg


class ChannelActions:

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def add_channel(
            self, channel_id: int,
            channel_name: str,
            channel_username: str,
            channel_url: str,
            channel_status: str = "True"
    ):
        query = """
            INSERT INTO channels(channel_id, channel_name, channel_username, channel_status, channel_url) VALUES($1, $2, $3, $4, $5)      
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, channel_id, channel_name, channel_username, channel_status, channel_url)

    async def add_channel_message(self, channel_id: int, channel_message: str):
        query = """
            UPDATE channels
            SET message = $1
            WHERE channel_id = $2
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, channel_message, channel_id)

    async def get_channel(self, channel_id: int):
        query = """
            SELECT * FROM channels WHERE channel_id = $1
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, channel_id)

    async def get_all_channels(self):
        query = """
            SELECT * FROM channels
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch(query)

    async def get_channel_message(self, channel_id: int):
        query = """
            SELECT message FROM channels WHERE channel_id = $1
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, channel_id)

    async def update_channel_status(self, new_channel_status: str, channel_id: int):
        query = """
            UPDATE channels SET channel_status = $1 WHERE channel_id = $2
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, new_channel_status, channel_id)

    async def delete_channel(self, channel_id: int):
        query = """
            DELETE FROM channels WHERE channel_id = $1 
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, channel_id)

    async def delete_channel_message(self, channel_id: int):
        query = """
            UPDATE channels
            SET message = NULL
            WHERE id = $1
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, channel_id)
