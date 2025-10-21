import asyncpg


class MiniSeriesActions:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def add_mini_series(
            self,
            mini_series_code: int,
            mini_series_name: str,
            series: int,
            video_file_id: str,
            caption: str,
    ):
        query = """
                INSERT INTO mini_series(code, name, series, video_file_id, captions) VALUES($1, $2, $3, $4, $5)  
        """

        async with self.pool.acquire() as conn:
            await conn.execute(query, int(mini_series_code), mini_series_name, int(series), video_file_id, caption)

    async def get_mini_series(self, mini_series_code: int):
        query = """
            SELECT * 
            FROM mini_series
            WHERE code = $1
        """

        async with self.pool.acquire() as conn:
            return await conn.fetch(query, mini_series_code)

    async def delete_mini_series(self, mini_series_code):
        query = """
                DELETE FROM mini_series WHERE code = $1 
            """
        async with self.pool.acquire() as conn:
            await conn.execute(query, mini_series_code)

    async def delete_mini_series_for_series(self, mini_series_code: int, series: int):
        query = """
            DELETE FROM mini_series
            WHERE code = $1 AND series = $2
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, mini_series_code, series)


