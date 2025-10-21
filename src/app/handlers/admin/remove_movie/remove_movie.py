from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.app.database.queries.movie.feature_films import FeatureFilmsActions
from src.app.database.queries.movie.mini_series import MiniSeriesActions
from src.app.database.queries.movie.series import SeriesActions
from src.app.keyboards.callback_data import DeleteMovie
from src.app.keyboards.inline import confirm_delete_kbd, mini_series_choice_kbd, series_choice_kbd, \
    back_to_admin_menu_kbd
from src.app.states.admin.movie import DeleteMovieSG

delete_router = Router()

@delete_router.callback_query(DeleteMovie.filter())
async def process_delete(call: CallbackQuery, callback_data: DeleteMovie, pool, state: FSMContext):
    try:
        # Полнометражный фильм
        if callback_data.action == "delete_feature_film":
            feature_films_actions = FeatureFilmsActions(pool)
            await feature_films_actions.delte_feature_film(callback_data.code)
            await call.message.answer("[OK] Фильм удалён.")
            await state.clear()
            return

        # Мини-сериал — удалить полностью
        if callback_data.action == "delete_mini_series_all":
            mini_series_actions = MiniSeriesActions(pool)
            await mini_series_actions.delete_mini_series(callback_data.code)
            await call.message.answer("[OK] Мини-сериал полностью удалён.")
            await state.clear()
            return

        # Мини-сериал — удалить только эпизод
        if callback_data.action == "delete_mini_series_epizod":
            await call.message.answer("[?] Какой эпизод вы хотите удалить? (введите номер)")
            await state.update_data(code=callback_data.code, type="mini_series")
            await state.set_state(DeleteMovieSG.send_movie_series)
            return

        # Сериал — удалить полностью
        if callback_data.action == "delete_series_all":
            series_actions = SeriesActions(pool)
            await series_actions.delete_series(callback_data.code)
            await call.message.answer("[OK] Сериал полностью удалён.")
            await state.clear()
            return

        # Сериал — удалить сезон
        if callback_data.action == "delete_series_season":
            await call.message.answer("[?] Какой сезон вы хотите удалить? (введите номер)")
            await state.update_data(code=callback_data.code)
            await state.set_state(DeleteMovieSG.send_movie_season)
            return

        # Сериал — удалить эпизод
        if callback_data.action == "delete_series_epizod":
            await call.message.answer("[?] В каком сезоне находится серия? (введите номер)")
            await state.update_data(code=callback_data.code, type="series")
            await state.set_state(DeleteMovieSG.send_series_season)
            return

    except Exception as e:
        print("ОШИБКА:", e)
        await call.message.answer("[X] Произошла ошибка при удалении.", reply_markup=back_to_admin_menu_kbd)


@delete_router.message(DeleteMovieSG.send_movie_code)
async def delete_start(message: Message, pool, state: FSMContext):
    code = int(message.text)
    await state.update_data(code=code)

    feature_films_actions = FeatureFilmsActions(pool)
    mini_series_actions = MiniSeriesActions(pool)
    series_actions = SeriesActions(pool)

    feature_film = await feature_films_actions.get_feature_film(code)
    mini_series = await mini_series_actions.get_mini_series(code)
    series = await series_actions.get_series(code)

    if feature_film:
        await message.answer(
            "[ФИЛЬМ] Этот код принадлежит полнометражному фильму. Удалить его?",
            reply_markup=confirm_delete_kbd(code, action="delete_feature_film")
        )

    elif mini_series:
        await message.answer(
            "[МИНИ-СЕРИАЛ] Этот код относится к мини-сериалу. Как вы хотите удалить?",
            reply_markup=mini_series_choice_kbd(code)
        )

    elif series:
        await message.answer(
            "[СЕРИАЛ] Этот код относится к сериалу. Как вы хотите удалить?",
            reply_markup=series_choice_kbd(code)
        )

    else:
        await message.answer("[X] Фильм не найден.")


@delete_router.message(DeleteMovieSG.send_series_season)
async def ask_series_number(message: Message, state: FSMContext):
    season_number = message.text
    if not season_number.isdigit():
        await message.answer("[!] Пожалуйста, введите только число.")
        return

    await state.update_data(season=int(season_number))
    await message.answer("[?] Какой эпизод вы хотите удалить? (введите номер)")
    await state.set_state(DeleteMovieSG.send_movie_series)


@delete_router.message(DeleteMovieSG.send_movie_season)
async def delete_season(message: Message, pool, state: FSMContext):
    data = await state.get_data()
    code = data.get("code")
    season_number = message.text

    if not season_number.isdigit():
        await message.answer("[!] Пожалуйста, введите только число.")
        return

    series_actions = SeriesActions(pool)
    await series_actions.delete_season(code, int(season_number))
    await message.answer(f"[OK] {season_number}-й сезон удалён.", reply_markup=back_to_admin_menu_kbd)
    await state.clear()


@delete_router.message(DeleteMovieSG.send_movie_series)
async def delete_epizod(message: Message, pool, state: FSMContext):
    data = await state.get_data()
    code = data.get("code")
    type_ = data.get("type")
    epizod_number = message.text

    if not epizod_number.isdigit():
        await message.answer("[!] Пожалуйста, введите только число.")
        return

    epizod_number = int(epizod_number)

    if type_ == "mini_series":
        mini_series_actions = MiniSeriesActions(pool)
        await mini_series_actions.delete_mini_series_for_series(code, epizod_number)
        await message.answer(f"[OK] Эпизод {epizod_number} удалён.", reply_markup=back_to_admin_menu_kbd)

    elif type_ == "series":
        series_actions = SeriesActions(pool)
        await series_actions.delete_series_for_season(code, epizod_number, data["season"])
        await message.answer(f"[OK] Эпизод {epizod_number} удалён.", reply_markup=back_to_admin_menu_kbd)

    else:
        await message.answer("[X] Ошибка: тип не определён.")

    await state.clear()

