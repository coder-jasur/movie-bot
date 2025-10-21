
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.app.keyboards.inline import choose_movie_type, add_feature_films_menu_buttons, \
    add_series_menu_buttons, add_mini_series_menu_buttons
from src.app.states.admin.movie import AddMovieSG

add_movie_router = Router()


@add_movie_router.callback_query(F.data == "add_movie")
async def add_movie_menu(call: CallbackQuery):
    await call.message.edit_text(
        text="выберите действия",
        reply_markup=choose_movie_type
    )


@add_movie_router.callback_query(F.data == "feature_films")
async def add_movie_menu(call: CallbackQuery):
    await call.message.edit_text(
        text="выберите действия",
        reply_markup=add_feature_films_menu_buttons
    )


@add_movie_router.callback_query(F.data == "series")
async def add_movie_menu(call: CallbackQuery):
    await call.message.edit_text(
        text="выберите действия",
        reply_markup=add_series_menu_buttons
    )


@add_movie_router.callback_query(F.data == "mini_series")
async def add_movie_menu(call: CallbackQuery):
    await call.message.edit_text(
        text="выберите действия",
        reply_markup=add_mini_series_menu_buttons
    )


@add_movie_router.message(AddMovieSG.send_video)
async def get_movie_video_file_id(message: Message, state: FSMContext):
    if message.video:
        data = await state.get_data()
        await state.update_data(
            {
                "movie_video_file_id": message.video.file_id
            }
        )
        if data["movie_type"] == "feature_film":
            await message.answer(
                text="выберите действия",
                reply_markup=add_feature_films_menu_buttons
            )
        elif data["movie_type"] == "mini_series":
            await message.answer(
                text="выберите действия",
                reply_markup=add_mini_series_menu_buttons
            )
        elif data["movie_type"] == "series":
            await message.answer(
                text="выберите действия",
                reply_markup=add_series_menu_buttons
            )
    else:
        await message.answer("отправьте видео!")


@add_movie_router.message(AddMovieSG.send_captions)
async def get_movie_video_file_id(message: Message, state: FSMContext):
    if message.text:
        data = await state.get_data()
        await state.update_data(
            {
                "movie_captions": message.text
            }
        )
        if data["movie_type"] == "feature_film":
            await message.answer(
                text="выберите действия",
                reply_markup=add_feature_films_menu_buttons
            )
        elif data["movie_type"] == "mini_series":
            await message.answer(
                text="выберите действия",
                reply_markup=add_mini_series_menu_buttons
            )
        elif data["movie_type"] == "series":
            await message.answer(
                text="выберите действия",
                reply_markup=add_series_menu_buttons
            )
    else:
        await message.answer("отправьте тект!")


@add_movie_router.message(AddMovieSG.send_movie_name)
async def get_movie_video_file_id(message: Message, state: FSMContext):
    if message.text:
        data = await state.get_data()
        await state.update_data(
            {
                "movie_name": message.text
            }
        )
        if data["movie_type"] == "feature_film":
            await message.answer(
                text="выберите действия",
                reply_markup=add_feature_films_menu_buttons
            )
        elif data["movie_type"] == "mini_series":
            await message.answer(
                text="выберите действия",
                reply_markup=add_mini_series_menu_buttons
            )
        elif data["movie_type"] == "series":
            await message.answer(
                text="выберите действия",
                reply_markup=add_series_menu_buttons
            )
    else:
        await message.answer("отправьте тект!")


@add_movie_router.message(AddMovieSG.send_movie_code)
async def get_movie_video_file_id(message: Message, state: FSMContext):
    if (str(message.text)).isdigit():
        data = await state.get_data()
        await state.update_data(
            {
                "movie_code": message.text
            }
        )
        if data["movie_type"] == "feature_film":
            await message.answer(
                text="выберите действия",
                reply_markup=add_feature_films_menu_buttons
            )
        elif data["movie_type"] == "mini_series":
            await message.answer(
                text="выберите действия",
                reply_markup=add_mini_series_menu_buttons
            )
        elif data["movie_type"] == "series":
            await message.answer(
                text="выберите действия",
                reply_markup=add_series_menu_buttons
            )
    else:
        await message.answer("отправьте целое число!")


@add_movie_router.message(AddMovieSG.send_movie_series)
async def get_movie_video_file_id(message: Message, state: FSMContext):
    if (str(message.text)).isdigit():
        data = await state.get_data()
        await state.update_data(
            {
                "movie_series": message.text
            }
        )
        if data["movie_type"] == "feature_film":
            await message.answer(
                text="выберите действия",
                reply_markup=add_feature_films_menu_buttons
            )
        elif data["movie_type"] == "mini_series":
            await message.answer(
                text="выберите действия",
                reply_markup=add_mini_series_menu_buttons
            )
        elif data["movie_type"] == "series":
            await message.answer(
                text="выберите действия",
                reply_markup=add_series_menu_buttons
            )
    else:
        await message.answer("отправьте целое число!")


@add_movie_router.message(AddMovieSG.send_movie_season)
async def get_movie_video_file_id(message: Message, state: FSMContext):
    if (str(message.text)).isdigit():
        data = await state.get_data()
        await state.update_data(
            {
                "movie_season": message.text
            }
        )
        if data["movie_type"] == "feature_film":
            await message.answer(
                text="выберите действия",
                reply_markup=add_feature_films_menu_buttons
            )
        elif data["movie_type"] == "mini_series":
            await message.answer(
                text="выберите действия",
                reply_markup=add_mini_series_menu_buttons
            )
        elif data["movie_type"] == "series":
            await message.answer(
                text="выберите действия",
                reply_markup=add_series_menu_buttons
            )
    else:
        await message.answer("отправьте целое число!")
