import logging
from sqlalchemy import select, String, cast
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database.models import (
    FeatureFilm, Series, MiniSeries,
    MultiFilmFeature, MultiFilmSeries, MultiFilmMiniSeries,
    AnimeFeature, AnimeSeries, AnimeMiniSeries
)

logger = logging.getLogger(__name__)


class SearchRepository:
    """Film qidirish - PostgreSQL ILIKE bilan optimallashtirilgan (JSON support)"""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search_feature_films(self, query: str, limit: int = 20) -> list[tuple]:
        """Barcha toifadagi feature filmlarni qidirish."""
        try:
            results = []
            for model in [FeatureFilm, MultiFilmFeature, AnimeFeature]:
                # Search in JSON names by casting to text
                stmt = select(model).where(cast(model.name, String).ilike(f"%{query}%")).limit(limit)
                res = await self.session.execute(stmt)
                films = res.scalars().all()
                for film in films:
                    score = self._calculate_score(film.name, query)
                    results.append((film, score))
            
            # Score bo'yicha tartiblash
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]
        except Exception as e:
            logger.error(f"Error searching feature films: {e}")
            return []

    def _calculate_score(self, name_obj: any, query: str) -> int:
        query_lower = query.lower()
        
        # If it's a dictionary (localized names), check all values
        if isinstance(name_obj, dict):
            max_score = 0
            for name in name_obj.values():
                if not name: continue
                score = self._get_single_score(str(name).lower(), query_lower)
                if score > max_score:
                    max_score = score
            return max_score or 80
        
        return self._get_single_score(str(name_obj).lower(), query_lower)

    def _get_single_score(self, name_lower: str, query_lower: str) -> int:
        if name_lower == query_lower: return 100
        if name_lower.startswith(query_lower): return 95
        if query_lower in name_lower: return 90
        return 85

    async def search_series(self, query: str, limit: int = 20) -> list[tuple]:
        """Barcha toifadagi seriallarni qidirish."""
        try:
            results = []
            for model in [Series, MultiFilmSeries, AnimeSeries]:
                stmt = select(model).where(cast(model.name, String).ilike(f"%{query}%")).distinct(model.code).limit(limit)
                res = await self.session.execute(stmt)
                series_list = res.scalars().all()
                for series in series_list:
                    score = self._calculate_score(series.name, query)
                    results.append((series, score))
            
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]
        except Exception as e:
            logger.error(f"Error searching series: {e}")
            return []

    async def search_mini_series(self, query: str, limit: int = 20) -> list[tuple]:
        """Barcha toifadagi mini-seriallarni qidirish."""
        try:
            results = []
            for model in [MiniSeries, MultiFilmMiniSeries, AnimeMiniSeries]:
                stmt = select(model).where(cast(model.name, String).ilike(f"%{query}%")).distinct(model.code).limit(limit)
                res = await self.session.execute(stmt)
                mini_list = res.scalars().all()
                for mini in mini_list:
                    score = self._calculate_score(mini.name, query)
                    results.append((mini, score))
            
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]
        except Exception as e:
            logger.error(f"Error searching mini series: {e}")
            return []

