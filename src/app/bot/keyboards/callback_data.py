import enum

from aiogram.filters.callback_data import CallbackData


class FeatureFilmPlayerCD(CallbackData, prefix="ff_p"):
    code: int
    actions: str
    quality: str | None = None
    language: str | None = None

class MiniSeriesPlayerCD(CallbackData, prefix="ms_p"):
    code: int
    series_number: int
    action: str
    quality: str | None = None
    language: str | None = None

class SeriesPlayerCD(CallbackData, prefix="s_p"):
    code: int
    series_number: int
    season_number: int
    all_series_numebr: int
    action: str
    quality: str | None = None
    language: str | None = None


class ActionType(str, enum.Enum):
    back_series = "back_series"
    next_series = "next_series"
    back_season = "back_season"
    next_season = "next_season"
    save_to_favorites = "save_to_favorites"
    remove_in_favorites = "remove_in_favorites"
    open_quality_menu = "open_quality_menu"
    close_quality_menu = "close_quality_menu"
    set_quality = "set_quality"
    open_language_menu = "open_language_menu"
    set_language = "set_language"
    open_series_menu = "open_series_menu"
    open_seasons_menu = "open_seasons_menu"


class ReferralCD(CallbackData, prefix="referral"):
    action: str
    id: int = 0


class LanguageCD(CallbackData, prefix="lang"):
    code: str
