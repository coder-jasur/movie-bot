import asyncpg
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.app.database.queries.movie.series import SeriesActions
from src.app.keyboards.callback_data import SeriesCD
from src.app.states.admin.movie import AddMovieSG

series_router = Router()

@series_router.callback_query(SeriesCD.filter())
async def add_series(call: CallbackQuery, callback_data: SeriesCD, state: FSMContext, pool: asyncpg.Pool):
    series_actions = SeriesActions(pool)

    await state.update_data(
        {
            "movie_type": "series"
        }
    )

    if callback_data.actions == "add_movie_media":
        await state.set_state(AddMovieSG.send_video)
        await call.message.edit_text("отправьте фильм")

    elif callback_data.actions == "add_movie_caption":
        await state.set_state(AddMovieSG.send_captions)
        await call.message.edit_text("отправитье описания фильма")


    elif callback_data.actions == "add_movie_series":
        await state.set_state(AddMovieSG.send_movie_series)
        await call.message.edit_text("отправьте эпизод фильма")

    elif callback_data.actions == "add_movie_season":
        await state.set_state(AddMovieSG.send_movie_season)
        await call.message.edit_text("отправьте сезон фильма")

    elif callback_data.actions == "add_movie_code":
        await state.set_state(AddMovieSG.send_movie_code)
        await call.message.edit_text("отправитье код фильма")

    elif callback_data.actions == "add_movie_name":
        await state.set_state(AddMovieSG.send_movie_name)
        await call.message.edit_text("отправитье название фильма")

    if callback_data.actions == "add_movie":
        data = await state.get_data()

        required_fields = {
            "movie_code": "вы не добавили код",
            "movie_name": "вы не добавили название",
            "movie_series": "вы не добавили эпизод",
            "movie_season": "вы не добавили сезон",
            "movie_video_file_id": "вы не добавили видео",
            "movie_captions": "вы не добавили описание",
        }

        for key, message in required_fields.items():
            if key not in data or not data[key]:
                await call.answer(message)
                return

        try:
            await series_actions.add_series(
                data["movie_code"],
                data["movie_name"],
                data["movie_series"],
                data["movie_season"],
                data["movie_video_file_id"],
                data["movie_captions"],
            )
            await call.message.answer("🎬 Фильм успешно добавлен!")
        except Exception as e:
            print("ERROR", e)
            await call.message.answer("❌ Не удалось добавить фильм.")
        finally:
            await state.clear()