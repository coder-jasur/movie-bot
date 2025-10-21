from aiogram.fsm.state import State, StatesGroup


class AddMovieSG(StatesGroup):
    send_movie_code = State()
    send_movie_name = State()
    send_video = State()
    send_captions = State()
    send_movie_series = State()
    send_movie_season = State()


class DeleteMovieSG(StatesGroup):
    send_series_season = State()
    send_movie_type = State()
    send_movie_code = State()
    send_movie_season = State()
    send_movie_series = State()
