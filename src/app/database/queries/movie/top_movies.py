from datetime import datetime, timedelta
from sqlalchemy import select, func, literal, union_all, or_
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.app.database.models import (
    FeatureFilm, Series, MiniSeries, Favorite,
    MultiFilmFeature, MultiFilmSeries, MultiFilmMiniSeries,
    AnimeFeature, AnimeSeries, AnimeMiniSeries
)

logger = logging.getLogger(__name__)


class TopMoviesActions:
    """Top filmlar uchun optimallashtirilgan query'lar"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_top_movies(self, interval: str = "total", limit: int = 20, category: str = "all") -> list[dict]:
        """Top filmlarni olish - database darajasida agregatsiya
        
        Args:
            interval: 'day' | 'week' | 'month' | 'total'
            limit: Nechta film qaytarish
            category: 'all' | 'cinema' | 'anime' | 'cartoon'
            
        Returns:
            List of dicts with movie info and stats
        """
        try:
            # Interval uchun filter
            start_date = self._get_start_date(interval)
            
            # Helpers for movie type labels
            types = {
                "film": ("Film", "Serial", "Epizodli film"),
                "multi_film": ("Multfilm", "Multserial", "Epizodli multfilm"),
                "anime": ("Anime (film)", "Anime (serial)", "Anime (mini)")
            }

            def get_feature_query(model, label):
                q = select(
                    model.code.label("code"),
                    model.name.label("name"),
                    literal(label).label("type"),
                    func.coalesce(func.count(func.distinct(Favorite.user_id)), 0).label("favs"),
                    model.views_count.label("views"),
                    (func.coalesce(func.count(func.distinct(Favorite.user_id)), 0) * 10 + model.views_count).label("score")
                ).outerjoin(Favorite, model.code == Favorite.movie_code)
                if start_date: q = q.where(Favorite.created_at >= start_date)
                return q.group_by(model.code, model.name, model.views_count)

            def get_series_query(model, label):
                q = select(
                    model.code.label("code"),
                    func.max(model.name).label("name"),
                    literal(label).label("type"),
                    func.coalesce(func.count(func.distinct(Favorite.user_id)), 0).label("favs"),
                    func.sum(model.views_count).label("views"),
                    (func.coalesce(func.count(func.distinct(Favorite.user_id)), 0) * 10 + func.sum(model.views_count)).label("score")
                ).outerjoin(Favorite, model.code == Favorite.movie_code)
                if start_date: q = q.where(Favorite.created_at >= start_date)
                return q.group_by(model.code)

            # Define queries for each category
            queries = []
            
            # Cinema
            if category in ["all", "cinema"]:
                queries.extend([
                    get_feature_query(FeatureFilm, types["film"][0]),
                    get_series_query(Series, types["film"][1]),
                    get_series_query(MiniSeries, types["film"][2]),
                ])

            # Cartoon
            if category in ["all", "cartoon"]:
                queries.extend([
                    get_feature_query(MultiFilmFeature, types["multi_film"][0]),
                    get_series_query(MultiFilmSeries, types["multi_film"][1]),
                    get_series_query(MultiFilmMiniSeries, types["multi_film"][2]),
                ])
                
            # Anime
            if category in ["all", "anime"]:
                queries.extend([
                    get_feature_query(AnimeFeature, types["anime"][0]),
                    get_series_query(AnimeSeries, types["anime"][1]),
                    get_series_query(AnimeMiniSeries, types["anime"][2]),
                ])
            
            if not queries:
                return []
            
            combined_query = union_all(*queries).subquery()
            
            # Final query - sorting va limit
            final_query = (
                select(combined_query)
                .order_by(combined_query.c.score.desc())
                .limit(limit)
            )
            
            result = await self.session.execute(final_query)
            rows = result.all()
            
            # Dict'ga konvertatsiya
            movies = []
            for row in rows:
                movies.append({
                    "code": row.code,
                    "name": row.name,
                    "type": row.type,
                    "favs": row.favs,
                    "views": row.views,
                    "score": row.score
                })
            
            return movies
            
        except Exception as e:
            logger.error(f"Error getting top movies: {e}")
            return []
    
    async def get_top_by_genres(self, genres: list[str], limit: int = 10, category: str = "all") -> list[dict]:
        """Janrlar bo'yicha top filmlarni olish
        
        Args:
            genres: Tanlangan janrlar ro'yxati
            limit: Natijalar soni
            category: 'all' | 'cinema' | 'anime' | 'cartoon'
            
        Returns:
            List of dicts with movie info
        """
        try:
            if not genres:
                return []
            
            # LIKE operatori uchun filterlarni tayyorlash
            # JSON array ichidan qidirish: %"JanrName"%
            genre_filters = [f'%"{g}"%' for g in genres]
            
            types = {
                "film": ("Film", "Serial", "Epizodli film"),
                "multi_film": ("Multfilm", "Multserial", "Epizodli multfilm"),
                "anime": ("Anime (film)", "Anime (serial)", "Anime (mini)")
            }

            def get_feature_genres_query(model, label):
                return (
                    select(
                        model.code.label("code"),
                        model.name.label("name"),
                        literal(label).label("type"),
                        model.genres.label("genres"),
                        func.coalesce(func.count(func.distinct(Favorite.user_id)), 0).label("favs"),
                        model.views_count.label("views"),
                        (func.coalesce(func.count(func.distinct(Favorite.user_id)), 0) * 10 + model.views_count).label("score")
                    ).outerjoin(Favorite, model.code == Favorite.movie_code)
                    .where(or_(*[model.genres.like(f) for f in genre_filters]))
                    .group_by(model.code, model.name, model.views_count, model.genres)
                )

            def get_series_genres_query(model, label):
                return (
                    select(
                        model.code.label("code"),
                        func.max(model.name).label("name"),
                        literal(label).label("type"),
                        model.genres.label("genres"),
                        func.coalesce(func.count(func.distinct(Favorite.user_id)), 0).label("favs"),
                        func.sum(model.views_count).label("views"),
                        (func.coalesce(func.count(func.distinct(Favorite.user_id)), 0) * 10 + func.sum(model.views_count)).label("score")
                    ).outerjoin(Favorite, model.code == Favorite.movie_code)
                    .where(or_(*[model.genres.like(f) for f in genre_filters]))
                    .group_by(model.code, model.genres)
                )

            # Define queries for each category
            queries = []
            
            # Cinema
            if category in ["all", "cinema"]:
                queries.extend([
                    get_feature_genres_query(FeatureFilm, types["film"][0]),
                    get_series_genres_query(Series, types["film"][1]),
                    get_series_genres_query(MiniSeries, types["film"][2]),
                ])

            # Cartoon
            if category in ["all", "cartoon"]:
                queries.extend([
                    get_feature_genres_query(MultiFilmFeature, types["multi_film"][0]),
                    get_series_genres_query(MultiFilmSeries, types["multi_film"][1]),
                    get_series_genres_query(MultiFilmMiniSeries, types["multi_film"][2]),
                ])
                
            # Anime
            if category in ["all", "anime"]:
                queries.extend([
                    get_feature_genres_query(AnimeFeature, types["anime"][0]),
                    get_series_genres_query(AnimeSeries, types["anime"][1]),
                    get_series_genres_query(AnimeMiniSeries, types["anime"][2]),
                ])

            if not queries:
                 return []
            
            combined_query = union_all(*queries).subquery()
            
            final_query = (
                select(combined_query)
                .order_by(combined_query.c.score.desc())
                .limit(limit)
            )
            
            result = await self.session.execute(final_query)
            rows = result.all()
            
            movies = []
            for row in rows:
                movies.append({
                    "code": row.code,
                    "name": row.name,
                    "type": row.type,
                    "favs": row.favs,
                    "views": row.views,
                    "score": row.score,
                    "genres": row.genres
                })
            
            return movies
            
        except Exception as e:
            logger.error(f"Error getting top by genres: {e}")
            return []

    def _get_start_date(self, interval: str) -> datetime | None:
        """Interval uchun start date hisoblash"""
        if interval == "total":
            return None
        
        now = datetime.now()
        
        if interval == "day":
            return now - timedelta(days=1)
        elif interval == "week":
            return now - timedelta(days=7)
        elif interval == "month":
            return now - timedelta(days=30)
        elif interval == "year":
            return now - timedelta(days=365)
        
        return None
