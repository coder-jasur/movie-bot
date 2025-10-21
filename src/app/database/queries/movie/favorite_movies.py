import asyncpg


class FavoriteMoviesActions:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def add_favorite_movie(
            self,
            movie_code: int,
            user_id: int
    ):
        query = """
            INSERT INTO favorites(user_id, movie_code)
            VALUES($1, $2)
            ON CONFLICT (user_id, movie_code) DO NOTHING
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, int(user_id), int(movie_code))

    async def get_favorites(
            self,
            movie_code: int,
            user_id: int
    ):
        query = """
            SELECT *
            FROM favorites
            WHERE user_id = $1 AND movie_code = $2
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, user_id, movie_code)

    async def get_all_favorites(self, user_id: int):
        query = """
            SELECT *
            FROM favorites
            WHERE user_id = $1
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, int(user_id))

    async def delete_favorite_movie(self, movie_code: int, user_id: int):
        query = """
            DELETE FROM favorites
            WHERE user_id = $1 AND movie_code = $2
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, user_id, movie_code)
