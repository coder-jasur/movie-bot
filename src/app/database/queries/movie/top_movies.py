import logging
from datetime import datetime, timedelta

from sqlalchemy import Text, and_, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database.models import (
    AnimeFeature,
    AnimeMiniSeries,
    AnimeSeries,
    Favorite,
    FeatureFilm,
    MiniSeries,
    MultiFilmFeature,
    MultiFilmMiniSeries,
    MultiFilmSeries,
    Series,
)

logger = logging.getLogger(__name__)


# Tarjima kerak bo'lmagan, faqat DB'da saqlanadigan type labellar
TYPE_LABELS = {
    "film_feature": "Film",
    "film_series": "Serial",
    "film_mini": "Epizodli film",
    "multi_feature": "Multfilm",
    "multi_series": "Multserial",
    "multi_mini": "Epizodli multfilm",
    "anime_feature": "Anime (film)",
    "anime_series": "Anime (serial)",
    "anime_mini": "Anime (mini)",
}


class TopMoviesActions:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_top_movies(
        self, interval: str = "total", limit: int = 20, category: str = "all"
    ) -> list[dict]:
        try:
            start_date = self._get_start_date(interval)

            def feature_query(model, type_key):
                fav_filter = [model.code == Favorite.movie_code]
                if start_date:
                    fav_filter.append(Favorite.created_at >= start_date)

                fav_count = func.coalesce(
                    func.count(func.distinct(Favorite.user_id)), 0
                )
                views = func.coalesce(model.views_count, 0)
                name_as_text = model.name.cast(Text)
                return (
                    select(
                        model.code.label("code"),
                        name_as_text.label("name"),
                        literal(type_key).label("type"),
                        fav_count.label("favs"),
                        views.label("views"),
                        (fav_count * 10 + views).label("score"),
                    )
                    .outerjoin(Favorite, and_(*fav_filter))
                    .group_by(model.code, name_as_text, model.views_count)
                )

            def series_query(model, type_key):
                fav_filter = [model.code == Favorite.movie_code]
                if start_date:
                    fav_filter.append(Favorite.created_at >= start_date)

                fav_count = func.coalesce(
                    func.count(func.distinct(Favorite.user_id)), 0
                )
                views = func.coalesce(func.sum(model.views_count), 0)
                # Series uchun: bir code'da ko'p qatorlar bor, max(name::text) ishlatamiz
                return (
                    select(
                        model.code.label("code"),
                        func.max(model.name.cast(Text)).label("name"),
                        literal(type_key).label("type"),
                        fav_count.label("favs"),
                        views.label("views"),
                        (fav_count * 10 + views).label("score"),
                    )
                    .outerjoin(Favorite, and_(*fav_filter))
                    .group_by(model.code)
                )

            queries = []
            if category in ("all", "cinema"):
                queries += [
                    feature_query(FeatureFilm, "film_feature"),
                    series_query(Series, "film_series"),
                    series_query(MiniSeries, "film_mini"),
                ]
            if category in ("all", "cartoon"):
                queries += [
                    feature_query(MultiFilmFeature, "multi_feature"),
                    series_query(MultiFilmSeries, "multi_series"),
                    series_query(MultiFilmMiniSeries, "multi_mini"),
                ]
            if category in ("all", "anime"):
                queries += [
                    feature_query(AnimeFeature, "anime_feature"),
                    series_query(AnimeSeries, "anime_series"),
                    series_query(AnimeMiniSeries, "anime_mini"),
                ]

            if not queries:
                return []

            combined = union_all(*queries).subquery()
            final_q = select(combined).order_by(combined.c.score.desc()).limit(limit)

            result = await self.session.execute(final_q)
            rows = result.all()

            return [
                {
                    "code": r.code,
                    "name": _parse_json_name(r.name),
                    "type": TYPE_LABELS.get(r.type, r.type),
                    "favs": r.favs,
                    "views": r.views,
                    "score": r.score,
                }
                for r in rows
            ]

        except Exception as e:
            logger.exception("Error getting top movies: %s", e)
            return []

    async def get_top_by_genres(
        self, genres: list[str], limit: int = 10, category: str = "all"
    ) -> list[dict]:
        try:
            if not genres:
                return []

            # JSON array ichida qidirish — DB '"Комедия"' ko'rinishida saqlaydi
            # Har bir janr uchun ikkala variant (qo'shtirnoqli va qo'shtirnoqsiz) qidiramiz
            genre_filters = []
            for g in genres:
                genre_filters.append(f'%"{g}"%')  # exact JSON match: ["Комедия"]
                genre_filters.append(f"%{g}%")     # fallback: just the word

            def feature_genres_query(model, type_key):
                fav_count = func.coalesce(
                    func.count(func.distinct(Favorite.user_id)), 0
                )
                views = func.coalesce(model.views_count, 0)
                name_as_text = model.name.cast(Text)
                return (
                    select(
                        model.code.label("code"),
                        name_as_text.label("name"),
                        literal(type_key).label("type"),
                        model.genres.label("genres"),
                        fav_count.label("favs"),
                        views.label("views"),
                        (fav_count * 10 + views).label("score"),
                    )
                    .outerjoin(Favorite, model.code == Favorite.movie_code)
                    .where(or_(*[model.genres.ilike(f) for f in genre_filters]))
                    .group_by(model.code, name_as_text, model.views_count, model.genres)
                )

            def series_genres_query(model, type_key):
                fav_count = func.coalesce(
                    func.count(func.distinct(Favorite.user_id)), 0
                )
                views = func.coalesce(func.sum(model.views_count), 0)
                return (
                    select(
                        model.code.label("code"),
                        func.max(model.name.cast(Text)).label("name"),
                        literal(type_key).label("type"),
                        func.max(model.genres).label("genres"),
                        fav_count.label("favs"),
                        views.label("views"),
                        (fav_count * 10 + views).label("score"),
                    )
                    .outerjoin(Favorite, model.code == Favorite.movie_code)
                    .where(or_(*[model.genres.ilike(f) for f in genre_filters]))
                    .group_by(model.code)
                )

            queries = []
            if category in ("all", "cinema"):
                queries += [
                    feature_genres_query(FeatureFilm, "film_feature"),
                    series_genres_query(Series, "film_series"),
                    series_genres_query(MiniSeries, "film_mini"),
                ]
            if category in ("all", "cartoon"):
                queries += [
                    feature_genres_query(MultiFilmFeature, "multi_feature"),
                    series_genres_query(MultiFilmSeries, "multi_series"),
                    series_genres_query(MultiFilmMiniSeries, "multi_mini"),
                ]
            if category in ("all", "anime"):
                queries += [
                    feature_genres_query(AnimeFeature, "anime_feature"),
                    series_genres_query(AnimeSeries, "anime_series"),
                    series_genres_query(AnimeMiniSeries, "anime_mini"),
                ]

            if not queries:
                return []

            combined = union_all(*queries).subquery()
            final_q = select(combined).order_by(combined.c.score.desc()).limit(limit)

            result = await self.session.execute(final_q)
            rows = result.all()

            return [
                {
                    "code": r.code,
                    "name": _parse_json_name(r.name),
                    "type": TYPE_LABELS.get(r.type, r.type),
                    "genres": r.genres,
                    "favs": r.favs,
                    "views": r.views,
                    "score": r.score,
                }
                for r in rows
            ]

        except Exception as e:
            logger.exception("Error getting top by genres: %s", e)
            return []

    def _get_start_date(self, interval: str) -> datetime | None:
        if interval == "total":
            return None
        now = datetime.now()
        deltas = {
            "day": timedelta(days=1),
            "week": timedelta(days=7),
            "month": timedelta(days=30),
            "year": timedelta(days=365),
        }
        return now - deltas.get(interval, timedelta(days=0))


# ─── Helper ───────────────────────────────────────────────────────────────────


def _parse_json_name(raw: str | dict | None) -> dict | str:
    """
    DB dan kelgan name: JSON string yoki dict bo'lishi mumkin.
    movie_search.py dagi get_localized_name(m, lang) dict kutadi.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        import json

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return str(parsed)
        except (json.JSONDecodeError, ValueError):
            return raw
    return raw or ""
