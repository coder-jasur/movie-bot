from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from src.app.database.models import (
    User, FeatureFilm, Series, MiniSeries, Favorite,
    MultiFilmFeature, MultiFilmSeries, MultiFilmMiniSeries,
    AnimeFeature, AnimeSeries, AnimeMiniSeries
)

class BackupQueries:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_users(self) -> list[User]:
        result = await self.session.execute(select(User).order_by(User.created_at.asc()))
        return list(result.scalars().all())

    async def get_all_feature_films(self) -> list[FeatureFilm]:
        result = await self.session.execute(select(FeatureFilm))
        return list(result.scalars().all())

    async def get_all_series(self) -> list[Series]:
        result = await self.session.execute(select(Series))
        return list(result.scalars().all())

    async def get_all_mini_series(self) -> list[MiniSeries]:
        result = await self.session.execute(select(MiniSeries))
        return list(result.scalars().all())

    async def get_all_multi_film_features(self) -> list[MultiFilmFeature]:
        result = await self.session.execute(select(MultiFilmFeature))
        return list(result.scalars().all())

    async def get_all_multi_film_series(self) -> list[MultiFilmSeries]:
        result = await self.session.execute(select(MultiFilmSeries))
        return list(result.scalars().all())

    async def get_all_multi_film_mini_series(self) -> list[MultiFilmMiniSeries]:
        result = await self.session.execute(select(MultiFilmMiniSeries))
        return list(result.scalars().all())

    async def get_all_anime_features(self) -> list[AnimeFeature]:
        result = await self.session.execute(select(AnimeFeature))
        return list(result.scalars().all())

    async def get_all_anime_series(self) -> list[AnimeSeries]:
        result = await self.session.execute(select(AnimeSeries))
        return list(result.scalars().all())

    async def get_all_anime_mini_series(self) -> list[AnimeMiniSeries]:
        result = await self.session.execute(select(AnimeMiniSeries))
        return list(result.scalars().all())

    async def get_all_favorites(self) -> list[Favorite]:
        result = await self.session.execute(select(Favorite))
        return list(result.scalars().all())

    # ─────────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────────

    def _prepare_data(self, data: dict) -> dict:
        """JSON'dan kelgan matnlarni (datetime) bazaga moslash."""
        from datetime import datetime
        for k, v in data.items():
            if k.endswith("_at") and isinstance(v, str):
                try:
                    data[k] = datetime.fromisoformat(v)
                except Exception:
                    pass
        return data

    # ─────────────────────────────────────────────
    #  RESTORE METHODS
    # ─────────────────────────────────────────────

    async def restore_users(self, data_list: list[dict]):
        for data in data_list:
            ready_data = self._prepare_data(data)
            stmt = insert(User).values(**ready_data).on_conflict_do_nothing(index_elements=["tg_id"])
            await self.session.execute(stmt)

    async def restore_favorites(self, data_list: list[dict]):
        for data in data_list:
            ready_data = self._prepare_data(data)
            stmt = insert(Favorite).values(**ready_data).on_conflict_do_nothing(
                index_elements=["user_id", "movie_code"]
            )
            await self.session.execute(stmt)

    async def restore_records(self, model, data_list: list[dict], index_elements: list[str]):
        """Umumiy model uchun restore funksiyasi."""
        for data in data_list:
            ready_data = self._prepare_data(data)
            stmt = insert(model).values(**ready_data).on_conflict_do_nothing(index_elements=index_elements)
            await self.session.execute(stmt)
