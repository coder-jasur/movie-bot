import asyncpg
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.app.database.queries.movie.favorite_movies import FavoriteMoviesActions
from src.app.database.queries.movie.feature_films import FeatureFilmsActions
from src.app.database.queries.movie.mini_series import MiniSeriesActions
from src.app.database.queries.movie.series import SeriesActions

favorite_movies_router = Router()

@favorite_movies_router.message(Command("favorites"))
async def list_favorite_movies(message: Message, pool: asyncpg.Pool):
    try:
        favorites_actions = FavoriteMoviesActions(pool)

        favorite_films_data = await favorites_actions.get_all_favorites(user_id=message.from_user.id)

        texts = ""
        if favorite_films_data:
            texts += "📬 Коллекция фильмов\n\n"
            for favorite_film_data in favorite_films_data:
                feature_movies_actions = FeatureFilmsActions(pool)
                mini_series_actions = MiniSeriesActions(pool)
                series_actions = SeriesActions(pool)

                feature_movies_data = await feature_movies_actions.get_feature_film(favorite_film_data[1])
                mini_series_data = await mini_series_actions.get_mini_series(favorite_film_data[1])
                series_data = await series_actions.get_series(favorite_film_data[1])

                text = None

                if feature_movies_data:
                    text = f"{feature_movies_data[1]} - {favorite_film_data[1]}\n\n"
                elif mini_series_data:
                    text = f"{mini_series_data[0][1]} - {favorite_film_data[1]}\n\n"
                elif series_data:
                    text = f"{series_data[0][1]} - {favorite_film_data[1]}\n\n"

                texts += text

            texts += "Просто отправьте код боту и наслаждайтесь вашими любимыми фильмами"
        else:
            texts += "Вы ещё ничего не сохранили"

        await message.answer(texts)

    except Exception as e:
        print("ERROR", e)
        await message.answer("Произошла ошибка. Попробуйте снова")
