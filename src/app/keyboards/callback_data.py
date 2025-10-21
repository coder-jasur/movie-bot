import enum

from aiogram.filters.callback_data import CallbackData


class FeatureFilmsCD(CallbackData, prefix="feature_films"):
    actions: str


class MiniSeriesCD(CallbackData, prefix="mini_series"):
    actions: str

class SeriesCD(CallbackData, prefix="series"):
    actions: str

class FeatureFilmPlayerCD(CallbackData, prefix="feature_film_player"):
    code: int
    actions: str

class MiniSeriesPlayerCD(CallbackData, prefix="mini_series_player"):
    code: int
    series_number: int
    action: str

class SeriesPlayerCD(CallbackData, prefix="series_player"):
    code: int
    series_number: int
    season_number: int
    all_series_numebr: int
    action: str


class ActionType(str, enum.Enum):
    back_series = "back_series"
    next_series = "next_series"
    back_season = "back_season"
    next_season = "next_season"
    save_to_favorites = "save_to_favorites"
    remove_in_favorites = "remove_in_favorites"

class DeleteMovie(CallbackData, prefix="delete_movie"):
    code: int
    season: int = None
    series: int = None
    action: str


class ChannelsCD(CallbackData, prefix="chanels_call"):
    channel_id: int
    actions: str

class BotCD(CallbackData, prefix="bot_call"):
    bot_username: str
    actions: str
