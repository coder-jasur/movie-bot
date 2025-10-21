import asyncpg


class FeatureFilmsActions:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def add_feature_film(
            self,
            film_code: int,
            film_name: str,
            video_file_id: str,
            caption: str,
    ):
        query = """
                INSERT INTO feature_films(code, name, video_file_id, captions) VALUES($1, $2, $3, $4)  
        """

        async with self.pool.acquire() as conn:
            await conn.execute(query, int(film_code), film_name, video_file_id, caption)

    async def get_feature_film(self, film_code: int):
        query = """
            SELECT * 
            FROM feature_films
            WHERE code = $1
        """

        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, film_code)

    async def delte_feature_film(self, film_code):
        query = """
                DELETE FROM feature_films WHERE code = $1 
            """
        async with self.pool.acquire() as conn:
            await conn.execute(query, film_code)