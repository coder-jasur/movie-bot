import asyncpg
from aiogram import Router
from aiogram.types import Message

from src.app.database.queries.movie.favorite_movies import FavoriteMoviesActions
from src.app.database.queries.movie.feature_films import FeatureFilmsActions
from src.app.database.queries.movie.mini_series import MiniSeriesActions
from src.app.database.queries.movie.series import SeriesActions
from src.app.filters.code import Code
from src.app.keyboards.inline import film_kbd, mini_series_player_kbd, series_player_kbd

send_movie_by_code_router = Router()
send_movie_by_code_router.message.filter(Code)


@send_movie_by_code_router.message()
async def send_movie_by_code(message: Message, pool: asyncpg.Pool):
    code = int(message.text)
    favorite_actions = FavoriteMoviesActions(pool)
    feature_films_actions = FeatureFilmsActions(pool)
    mini_series_actions = MiniSeriesActions(pool)
    series_actions = SeriesActions(pool)

    feature_films = await feature_films_actions.get_feature_film(code)
    mini_series = await mini_series_actions.get_mini_series(code)
    series = await series_actions.get_series(code)

    saved = await favorite_actions.get_favorites(code, message.from_user.id)

    saved = bool(saved)

    if feature_films:
        await message.answer_video(
            video=feature_films[2],
            caption=feature_films[-1],
            reply_markup=film_kbd(code, saved)
        )
    elif mini_series:
        await message.answer_video(
            video=mini_series[0][3],
            caption=mini_series[0][-1],
            reply_markup=mini_series_player_kbd(code, 1, len(mini_series), saved)
        )
    elif series:
        current_season_series = 0

        for s in series:
            if s[2] == 1:
                current_season_series += 1

        await message.answer_video(
            video=series[0][4],
            caption=series[0][5],
            reply_markup=series_player_kbd(
                code,
                1,
                len(series),
                1,
                series[-1][2],
                1,
                current_season_series,
                saved
            )
        )
    else:
        await message.answer("😔 Hechnima topilmadi.")
