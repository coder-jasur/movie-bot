import asyncpg


class SeriesActions:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool


    async def add_series(
            self,
            series_code: int,
            series_name: str,
            series: int,
            saeason: int,
            video_file_id: str,
            caption: str,
    ):
        query = """
                INSERT INTO series(code, name, season, series, video_file_id, captions) VALUES($1, $2, $3, $4, $5, $6)  
        """

        async with self.pool.acquire() as conn:
            await conn.execute(query, int(series_code), series_name, int(saeason), int(series), video_file_id, caption)

    async def get_series(self, series_code: int):
        query = """
            SELECT * 
            FROM series
            WHERE code = $1
        """

        async with self.pool.acquire() as conn:
            return await conn.fetch(query, series_code)

    async def delete_series(self, series_code):
        query = """
                DELETE FROM series WHERE code = $1 
            """
        async with self.pool.acquire() as conn:
            await conn.execute(query, series_code)

    async def delete_season(self, series_code: int, season: int):
        query = """
            DELETE FROM series
            WHERE code = $1 AND season = $2
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, series_code, season)


    async def delete_series_for_season(self, series_code: int, series: int, season: int):
        query = """
            DELETE FROM series
            WHERE code = $1 AND series = $2 AND season = $3
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, series_code, series, season)



