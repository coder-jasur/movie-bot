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
    {"name": "Эротика", "emoji": "🔞", "label": _("🔞 Эротика")},
]


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
        lang: Locale code (uz, ru, en)
        
    Returns:
        Formatted string with emojis
    """
    from src.app.bot.common.i18n import i18n
    if not genres:
        return i18n.gettext("Janr tanlanmagan", locale=lang)
    
    # Map of technical name to display name (translated for the specific language)
    genre_map = {g["name"]: i18n.gettext(str(g["label"]), locale=lang) for g in GENRES}

    display_genres = []
    for g in genres:
        display_genres.append(genre_map.get(g, g))
    
    return ", ".join(display_genres)
