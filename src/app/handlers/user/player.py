import asyncpg
from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaVideo

from src.app.database.queries.movie.favorite_movies import FavoriteMoviesActions
from src.app.database.queries.movie.mini_series import MiniSeriesActions
from src.app.database.queries.movie.series import SeriesActions
from src.app.keyboards.callback_data import SeriesPlayerCD, FeatureFilmPlayerCD, MiniSeriesPlayerCD
from src.app.keyboards.inline import series_player_kbd, film_kbd, mini_series_player_kbd

player_router = Router()


@player_router.callback_query(F.data == "close")
async def clouuse_window(call: CallbackQuery):
    await call.message.delete()


@player_router.callback_query(SeriesPlayerCD.filter())
async def series_player(call: CallbackQuery, pool: asyncpg.Pool, callback_data: SeriesPlayerCD):
    series_actions = SeriesActions(pool)
    favorites_actions = FavoriteMoviesActions(pool)

    series_data = await series_actions.get_series(callback_data.code)
    series_data_sorted = sorted(series_data, key=lambda s: (s[2], s[3]))
    print(callback_data.series_number)
    print(callback_data.season_number)

    current_series = next(
        (s for s in series_data_sorted
         if s[2] == callback_data.season_number and s[3] == callback_data.series_number),
        None
    )

    if current_series is None:
        await call.answer("❌ Серия не найдена", show_alert=True)
        return

    current_index = next(
        (i for i, s in enumerate(series_data_sorted, start=1)
         if s[2] == callback_data.season_number and s[3] == callback_data.series_number),
        1
    )

    series_count_for_current_season = sum(1 for s in series_data_sorted if s[2] == callback_data.season_number)

    series_count = len(series_data_sorted)
    seasons_count = max(s[2] for s in series_data_sorted)

    user_id = call.from_user.id
    saved = await favorites_actions.get_favorites(callback_data.code, user_id)

    if callback_data.action == "save_to_favorites":
        await favorites_actions.add_favorite_movie(callback_data.code, user_id)
        saved = True
    elif callback_data.action == "remove_in_favorites":
        await favorites_actions.delete_favorite_movie(callback_data.code, user_id)
        saved = False

    await call.message.edit_media(
        InputMediaVideo(
            media=current_series[4],
            caption=current_series[5]
        ),
        reply_markup=series_player_kbd(
            code=callback_data.code,
            current_series=current_index,
            series_count=series_count,
            current_season=callback_data.season_number,
            seasons_count=seasons_count,
            current_series_for_current_season=callback_data.series_number,
            series_count_for_current_season=series_count_for_current_season,
            saved=bool(saved)
        )
    )


@player_router.callback_query(FeatureFilmPlayerCD.filter())
async def feature_movies_player(call: CallbackQuery, callback_data: FeatureFilmPlayerCD, pool: asyncpg.Pool):
    favorite_films_actions = FavoriteMoviesActions(pool)

    saved = await favorite_films_actions.get_favorites(callback_data.code, call.from_user.id)
    saved = True if saved else False
    print(saved)

    if callback_data.actions == "delete_for_favorites" and saved:
        await favorite_films_actions.delete_favorite_movie(callback_data.code, call.from_user.id)
        await call.message.edit_reply_markup(
            reply_markup=film_kbd(callback_data.code, False)
        )
        return await call.answer("❌ Фильм удалён из избранного")

    if callback_data.actions == "add_to_favorites" and not saved:
        await favorite_films_actions.add_favorite_movie(callback_data.code, call.from_user.id)
        await call.message.edit_reply_markup(
            reply_markup=film_kbd(callback_data.code, True)
        )
        return await call.answer("💾 Фильм добавлен в избранное")


@player_router.callback_query(MiniSeriesPlayerCD.filter())
async def mini_series_player(call: CallbackQuery, callback_data: MiniSeriesPlayerCD, pool: asyncpg.Pool):
    favorite_films_actions = FavoriteMoviesActions(pool)
    mini_series_actions = MiniSeriesActions(pool)

    saved = await favorite_films_actions.get_favorites(callback_data.code, call.from_user.id)
    mini_series_data = await mini_series_actions.get_mini_series(callback_data.code)
    current_series = None
    for series in mini_series_data:
        print(series)
        if series[2] == callback_data.series_number:
            current_series = series
    saved = bool(saved)
    print(saved)

    if callback_data.action == "delete_for_favorites" and saved:
        await favorite_films_actions.delete_favorite_movie(callback_data.code, call.from_user.id)
        await call.message.edit_media(
            InputMediaVideo(media=current_series[3], caption=current_series[-1]),
            reply_markup=mini_series_player_kbd(callback_data.code, current_series[2], len(mini_series_data), False)
        )
        return await call.answer("❌ Фильм удалён из избранного")

    if callback_data.action == "add_to_favorites" and not saved:
        await favorite_films_actions.add_favorite_movie(callback_data.code, call.from_user.id)
        await call.message.edit_media(
            InputMediaVideo(media=current_series[3], caption=current_series[-1]),
            reply_markup=mini_series_player_kbd(callback_data.code, current_series[2], len(mini_series_data), True)
        )
        return await call.answer("💾 Фильм добавлен в избранное")

    if callback_data.action == "next_series":
        await call.message.edit_media(
            InputMediaVideo(media=current_series[3], caption=current_series[-1]),
            reply_markup=mini_series_player_kbd(callback_data.code, current_series[2], len(mini_series_data), saved)
        )

    if callback_data.action == "back_series":
        await call.message.edit_media(
            InputMediaVideo(media=current_series[3], caption=current_series[-1]),
            reply_markup=mini_series_player_kbd(callback_data.code, current_series[2], len(mini_series_data), saved)
        )
