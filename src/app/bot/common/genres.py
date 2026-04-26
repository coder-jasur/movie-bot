"""
Genre management module for Movie Bot.

This module contains all genre-related constants, configurations, and helper functions.
"""

import json
from typing import List, Optional

from src.app.bot.common.i18n import lazy_gettext as _

# All available genres with their emojis
# Technical names are in Russian for database consistency
GENRES = [
    {"name": "Драма", "emoji": "🎭", "label": _("🎭 Драма")},
    {"name": "Комедия", "emoji": "😂", "label": _("😂 Комедия")},
    {"name": "Боевик", "emoji": "💥", "label": _("💥 Боевик")},
    {"name": "Триллер", "emoji": "😱", "label": _("😱 Триллер")},
    {"name": "Ужасы", "emoji": "👻", "label": _("👻 Ужасы")},
    {"name": "Фантастика", "emoji": "🚀", "label": _("🚀 Фантастика")},
    {"name": "Фэнтези", "emoji": "🧙", "label": _("🧙 Фэнтези")},
    {"name": "Мелодрама", "emoji": "❤️", "label": _("❤️ Мелодрама")},
    {"name": "Детектив", "emoji": "🕵️", "label": _("🕵️ Детектив")},
    {"name": "Приключения", "emoji": "🗺️", "label": _("🗺️ Приключения")},
    {"name": "Семейный", "emoji": "👨‍👩‍👧", "label": _("👨‍👩‍👧 Семейный")},
    {"name": "Мультфильм", "emoji": "🐭", "label": _("🐭 Мультфильм")},
    {"name": "Исторический", "emoji": "🏛️", "label": _("🏛️ Исторический")},
    {"name": "Документальный", "emoji": "📚", "label": _("📚 Документальный")},
    {"name": "Военный", "emoji": "⚔️", "label": _("⚔️ Военный")},
    {"name": "Романтика", "emoji": "💕", "label": _("💕 Романтика")},
    {"name": "Криминал", "emoji": "🔫", "label": _("🔫 Криминал")},
    {"name": "Спорт", "emoji": "⚽", "label": _("⚽ Спорт")},
    {"name": "Биография", "emoji": "📖", "label": _("📖 Биография")},
    {"name": "Вестерн", "emoji": "🤠", "label": _("🤠 Вестерн")},
    {"name": "Мюзикл", "emoji": "🎵", "label": _("🎵 Мюзикл")},
    {"name": "Психологический", "emoji": "🧠", "label": _("🧠 Психологический")},
    {"name": "Аниме", "emoji": "🎌", "label": _("🎌 Аниме")},
    {"name": "Короткометражка", "emoji": "🎞️", "label": _("🎞️ Короткометражка")},
]

# Mapping from various languages to the internal Russian technical names
GENRE_MAPPING = {
    # English -> Russian
    "Action": "Боевик",
    "Adventure": "Приключения",
    "Animation": "Мультфильм",
    "Comedy": "Комедия",
    "Crime": "Криминал",
    "Documentary": "Документальный",
    "Drama": "Драма",
    "Family": "Семейный",
    "Fantasy": "Фэнтези",
    "History": "Исторический",
    "Horror": "Ужасы",
    "Music": "Мюзикл",
    "Musical": "Мюзикл",
    "Mystery": "Детектив",
    "Romance": "Романтика",
    "Science Fiction": "Фантастика",
    "Sci-Fi": "Фантастика",
    "TV Movie": "Телевизионный фильм",
    "Thriller": "Триллер",
    "War": "Военный",
    "Western": "Вестерн",
    "Psychological": "Психологический",
    "Anime": "Аниме",
    "Short": "Короткометражка",
    # Uzbek -> Russian
    "Jangari": "Боевик",
    "Sarguzasht": "Приключения",
    "Multfilm": "Мультфильм",
    "Komediya": "Комедия",
    "Kriminal": "Криминал",
    "Hujjatli": "Документальный",
    "Qorqinchli": "Ужасы",
    "Fentezi": "Фэнтези",
    "Tarixiy": "Исторический",
    "Detektiv": "Детектив",
    "Romantika": "Романтика",
    "Melodrama": "Мелодрама",
    "Fantastika": "Фантастика",
    "Harbiy": "Военный",
    "Vestern": "Вестерн",
    "Psixologik": "Психологический",
    "Qisqa metrajli": "Короткометражка",
    "Myuzikl": "Мюзикл",
    "Sport": "Спорт",
    "Biografiya": "Биография",
    "Oilaviy": "Семейный",
}


def map_to_internal_genre(genre_name: str) -> str:
    """
    Map an external genre name (from TMDB or manual input) to internal technical name.
    """
    if not genre_name:
        return genre_name
    return GENRE_MAPPING.get(genre_name, genre_name)


def serialize_genres(genres: List[str]) -> str:
    """
    Convert list of genre names to JSON string for database storage.
    """
    return json.dumps(genres, ensure_ascii=False)


def deserialize_genres(genres_json: Optional[str]) -> List[str]:
    """
    Convert JSON string from database to list of genre names.
    """
    if not genres_json:
        return []
    try:
        return json.loads(genres_json)
    except (json.JSONDecodeError, TypeError):
        return []


def get_genre_display_text(genres: List[str], lang: str = None) -> str:
    """
    Get formatted display text for selected genres.

    Args:
        genres: List of genre names (technical names in Russian)
        lang: Locale code (uz, ru, en). If None, uses current locale.

    Returns:
        Formatted string with emojis
    """
    from src.app.bot.common.i18n import i18n

    if not genres:
        return ""

    # Map of technical name to display name (translated for the specific language)
    genre_map = {g["name"]: i18n.gettext(str(g["label"]), locale=lang) for g in GENRES}

    display_genres = []
    for g in genres:
        # Ensure the genre is internal
        internal_g = map_to_internal_genre(g)
        display_genres.append(genre_map.get(internal_g, internal_g))

    return ", ".join(display_genres)
