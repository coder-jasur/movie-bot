import asyncpg
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.app.database.queries.movie.feature_films import FeatureFilmsActions
from src.app.keyboards.callback_data import FeatureFilmsCD
from src.app.states.admin.movie import AddMovieSG

feature_films_router = Router()

@feature_films_router.callback_query(FeatureFilmsCD.filter())
async def add_feature_films(call: CallbackQuery, pool: asyncpg.Pool, callback_data: FeatureFilmsCD, state: FSMContext):
    feature_films_actions = FeatureFilmsActions(pool)

    await state.update_data(
        {
            "movie_type": "feature_film"
        }
    )

    if callback_data.actions == "add_movie_media":
        await state.set_state(AddMovieSG.send_video)
        await call.message.edit_text("отправьте фильм")

    elif callback_data.actions == "add_movie_caption":
        await state.set_state(AddMovieSG.send_captions)
        await call.message.edit_text("отправитье описания фильма")


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
            "movie_video_file_id": "Вы не добавили видео!",
            "movie_captions": "Вы не добавили описание!",
        }

        for key, msg in required_fields.items():
            if key not in data or not data[key]:
                await call.message.answer(msg)
                return
        try:
            await feature_films_actions.add_feature_film(
                data["movie_code"],
                data["movie_name"],
                data["movie_video_file_id"],
                data["movie_captions"],
            )
            await call.message.answer("фильм успешо добавлен")
            await state.clear()
        except Exception as e:
            print("ERROR", e)
            await call.message.answer("не удалось добавить фильм")

