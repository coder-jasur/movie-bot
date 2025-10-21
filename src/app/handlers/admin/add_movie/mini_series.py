import asyncpg
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.app.database.queries.movie.mini_series import MiniSeriesActions
from src.app.keyboards.callback_data import MiniSeriesCD
from src.app.states.admin.movie import AddMovieSG

mini_series_router = Router()

@mini_series_router.callback_query(MiniSeriesCD.filter())
async def add_mini_series(call: CallbackQuery, callback_data: MiniSeriesCD, state: FSMContext, pool: asyncpg.Pool):
    mini_series_actions = MiniSeriesActions(pool)

    await state.update_data(
        {
            "movie_type": "mini_series"
        }
    )

    if callback_data.actions == "add_movie_media":
        await state.set_state(AddMovieSG.send_video)
        await call.message.edit_text("отправьте фильм")

    elif callback_data.actions == "add_movie_caption":
        await state.set_state(AddMovieSG.send_captions)
        await call.message.edit_text("отправитье описания фильма")

    if callback_data.actions == "add_movie_series":
        await state.set_state(AddMovieSG.send_movie_series)
        await call.message.edit_text("отправьте эпизод фильма")

    elif callback_data.actions == "add_movie_code":
        await state.set_state(AddMovieSG.send_movie_code)
        await call.message.edit_text("отправитье код фильма")

    elif callback_data.actions == "add_movie_name":
        await state.set_state(AddMovieSG.send_movie_name)
        await call.message.edit_text("отправитье название фильма")

    if callback_data.actions == "add_movie":
        data = await state.get_data()

        required_fields = {
            "movie_code": "Вы не добавили код!",
            "movie_name": "Вы не добавили название!",
            "movie_series": "Вы не добавили эпизод!",
            "movie_video_file_id": "Вы не добавили видео!",
            "movie_captions": "Вы не добавили описание!",
        }

        for key, msg in required_fields.items():
            if key not in data or not data[key]:
                await call.message.answer(msg)
                return

        try:
            await mini_series_actions.add_mini_series(
                data["movie_code"],
                data["movie_name"],
                data["movie_series"],
                data["movie_video_file_id"],
                data["movie_captions"],
            )
            await call.message.answer("Фильм успешно добавлен!")
        except Exception as e:
            print("ERROR", e)
            await call.message.answer("Не удалось добавить фильм.")
        finally:
            await state.clear()