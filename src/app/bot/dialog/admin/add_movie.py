import asyncio
import html
import logging
from typing import Any

logger = logging.getLogger(__name__)

from aiogram.enums import ContentType
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, ShowMode, Window
from aiogram_dialog.api.entities import MediaAttachment, MediaId
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (
    Button,
    Cancel,
    Column,
    Group,
    Row,
    Select,
    SwitchTo,
)
from aiogram_dialog.widgets.media import DynamicMedia
from aiogram_dialog.widgets.text import Const, Format
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.common.genres import (
    deserialize_genres,
    get_genre_display_text,
    serialize_genres,
)
from src.app.bot.common.i18n import lazy_gettext
from src.app.bot.common.i18n import lazy_gettext as _
from src.app.bot.common.languages import LANGUAGES
from src.app.bot.common.utils import get_lang_code, send_admin_preview_media_group
from src.app.bot.states.admin.dialogs import AddMovieWizardSG
from src.app.core.config import load_config
from src.app.database.queries.movie.anime import (
    AnimeFeatureActions,
    AnimeMiniSeriesActions,
    AnimeSeriesActions,
)
from src.app.database.queries.movie.feature_films import FeatureFilmsActions
from src.app.database.queries.movie.mini_series import MiniSeriesActions
from src.app.database.queries.movie.multi_films import (
    MultiFilmFeatureActions,
    MultiFilmMiniSeriesActions,
    MultiFilmSeriesActions,
)
from src.app.database.queries.movie.series import SeriesActions
from src.app.database.queries.post_channels import PostChannelActions
from src.app.services.tmdb import TMDBService
from src.app.services.transcoder import Transcoder


async def get_all_languages_for_code(session: AsyncSession, code: int):
    from sqlalchemy import text

    tables = [
        "feature_films",
        "series",
        "mini_series",
        "multi_film_features",
        "multi_film_series",
        "multi_film_mini_series",
    ]
    langs = set()
    for table in tables:
        try:
            stmt = text(f"SELECT language FROM {table} WHERE code = :code")
            result = await session.execute(stmt, {"code": code})
            for row in result.all():
                if row[0]:
                    langs.add(row[0])
        except:
            pass
    return list(langs)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────


def _reset_keys(data: dict, keys: list):
    """Safely pop a list of keys from dialog_data."""
    for k in keys:
        data.pop(k, None)


async def _get_existing_by_code(
    session: AsyncSession, code: int
) -> tuple[Any, str, str] | None:
    checks = [
        (FeatureFilmsActions, "feature_film", "cat_film", False),
        (SeriesActions, "series", "cat_film", True),
        (MiniSeriesActions, "mini_series", "cat_film", True),
        (MultiFilmFeatureActions, "feature_film", "cat_multi", False),
        (MultiFilmSeriesActions, "series", "cat_multi", True),
        (MultiFilmMiniSeriesActions, "mini_series", "cat_multi", True),
        (AnimeFeatureActions, "feature_film", "cat_anime", False),
        (AnimeSeriesActions, "series", "cat_anime", True),
        (AnimeMiniSeriesActions, "mini_series", "cat_anime", True),
    ]
    for ActionClass, m_type, cat, is_list in checks:
        actions = ActionClass(session)
        if m_type == "feature_film":
            result = await actions.get_feature_film(code)
        elif m_type == "series":
            result = await actions.get_series(code)
        else:
            result = await actions.get_mini_series(code)

        if result:
            return result, m_type, cat
    return None


# ─────────────────────────────────────────────
#  HANDLERS
# ─────────────────────────────────────────────


async def on_category_selected(
    c: CallbackQuery, widget: Button, manager: DialogManager
):
    manager.dialog_data["category"] = widget.widget_id
    await manager.next()


async def on_movie_type_selected(
    c: CallbackQuery, widget: Button, manager: DialogManager
):
    manager.dialog_data["movie_type"] = widget.widget_id
    await manager.next()


async def on_code_input(m: Message, widget: Any, manager: DialogManager):
    if not m.text.isdigit():
        await m.answer(str(_("❌ Faqat raqam kiriting!")))
        return

    code = int(m.text)
    manager.dialog_data["code"] = code
    session: AsyncSession = manager.middleware_data["session"]

    found = await _get_existing_by_code(session, code)
    if not found:
        manager.dialog_data["genres"] = []
        manager.dialog_data["existing_langs"] = []
        await manager.switch_to(AddMovieWizardSG.input_name)
        return

    result, exist_type, exist_cat = found

    if exist_type == "feature_film":
        obj = result
        existing_langs = (obj.language or "").split(",")
        genres_raw = obj.genres
        captions = obj.captions
        name = obj.name
    else:
        obj = result[0]
        existing_langs = (obj.language or "").split(",")
        genres_raw = obj.genres
        captions = obj.captions
        name = obj.name

    manager.dialog_data.update(
        {
            "exists": True,
            "exist_type": exist_type,
            "exist_cat": exist_cat,
            "name": name,
            "existing_langs": [l for l in existing_langs if l],
            "existing_captions": captions,
        }
    )
    if genres_raw:
        manager.dialog_data["genres"] = deserialize_genres(genres_raw)
    else:
        manager.dialog_data["genres"] = []

    await manager.switch_to(AddMovieWizardSG.quick_add)


async def on_add_language(c: CallbackQuery, widget: Any, manager: DialogManager):
    manager.dialog_data["is_adding_track"] = True
    manager.dialog_data["lang_mode"] = "new"

    current_type = manager.dialog_data.get("movie_type") or manager.dialog_data.get(
        "exist_type"
    )
    current_cat = manager.dialog_data.get("category") or manager.dialog_data.get(
        "exist_cat"
    )
    manager.dialog_data["movie_type"] = current_type
    manager.dialog_data["category"] = current_cat

    last_lang = manager.dialog_data.get("language")
    if last_lang:
        if "existing_langs" not in manager.dialog_data:
            manager.dialog_data["existing_langs"] = []
        if last_lang not in manager.dialog_data["existing_langs"]:
            manager.dialog_data["existing_langs"].append(last_lang)

    _reset_keys(
        manager.dialog_data,
        [
            "name",
            "file_id",
            "files",
            "caption",
            "editing_field",
            "format",
            "existing_captions",
            "language",
        ],
    )
    # Redirect to input_file so the user can upload the video for the new language.
    # The wizard will then naturally flow to input_caption and input_language.
    await manager.switch_to(AddMovieWizardSG.input_file)


async def on_quick_new_season(c: CallbackQuery, widget: Any, manager: DialogManager):
    await manager.switch_to(AddMovieWizardSG.input_season_number)


async def on_quick_next(c: CallbackQuery, widget: Any, manager: DialogManager):
    _reset_keys(
        manager.dialog_data,
        ["file_id", "files", "caption", "format", "is_adding_track", "language"],
    )
    manager.dialog_data["lang_mode"] = "existing"
    await manager.switch_to(AddMovieWizardSG.input_language)


async def on_name_input(m: Message, widget: Any, manager: DialogManager):
    lang = manager.dialog_data.get("language")
    if lang:
        lang_id = get_lang_code(lang)
        current_name = manager.dialog_data.get("name")
        if not isinstance(current_name, dict):
            current_name = {"uz": str(current_name)} if current_name else {}
        current_name[lang_id] = m.text
        manager.dialog_data["name"] = current_name
    else:
        manager.dialog_data["name"] = m.text

    session: AsyncSession = manager.middleware_data["session"]
    code = manager.dialog_data.get("code")
    movie_type = manager.dialog_data.get("movie_type")
    category = manager.dialog_data.get("category")

    genres_exist = False
    if movie_type == "series":
        actions = _get_series_actions(session, category)
        existing = await actions.get_series(code)
        if existing and existing[0].genres:
            manager.dialog_data["genres"] = deserialize_genres(existing[0].genres)
            genres_exist = True
    elif movie_type == "mini_series":
        actions = _get_mini_actions(session, category)
        existing = await actions.get_mini_series(code)
        if existing and existing[0].genres:
            manager.dialog_data["genres"] = deserialize_genres(existing[0].genres)
            genres_exist = True

    lang_already_set = bool(manager.dialog_data.get("language"))
    is_adding = manager.dialog_data.get("is_adding_track", False)

    if genres_exist or is_adding:
        if lang_already_set and movie_type in ["series", "mini_series"]:
            if movie_type == "series":
                await manager.switch_to(AddMovieWizardSG.input_season_number)
            else:
                await manager.switch_to(AddMovieWizardSG.input_series_number)
        elif movie_type in ["series", "mini_series"]:
            manager.dialog_data["lang_mode"] = "all"
            await manager.switch_to(AddMovieWizardSG.input_language)
        else:
            await manager.switch_to(AddMovieWizardSG.input_file)
    elif movie_type in ["series", "mini_series"]:
        if "genres" not in manager.dialog_data:
            manager.dialog_data["genres"] = []
        await manager.switch_to(AddMovieWizardSG.select_genres)
    else:
        await manager.switch_to(AddMovieWizardSG.input_file)


def _get_series_actions(session, category):
    if category == "multi_film":
        return MultiFilmSeriesActions(session)
    elif category == "anime":
        return AnimeSeriesActions(session)
    return SeriesActions(session)


def _get_mini_actions(session, category):
    if category == "multi_film":
        return MultiFilmMiniSeriesActions(session)
    elif category == "anime":
        return AnimeMiniSeriesActions(session)
    return MiniSeriesActions(session)


def _get_feature_actions(session, category):
    if category == "multi_film":
        return MultiFilmFeatureActions(session)
    elif category == "anime":
        return AnimeFeatureActions(session)
    return FeatureFilmsActions(session)


async def on_season_input(m: Message, widget: Any, manager: DialogManager):
    if not m.text.isdigit():
        await m.answer(str(_("❌ Raqam kiriting!")))
        return
    manager.dialog_data["season"] = int(m.text)
    await manager.switch_to(AddMovieWizardSG.input_series_number)


async def on_series_num_input(m: Message, widget: Any, manager: DialogManager):
    if not m.text.isdigit():
        await m.answer(str(_("❌ Raqam kiriting!")))
        return

    num = int(m.text)
    code = manager.dialog_data.get("code")
    movie_type = manager.dialog_data.get("movie_type")
    category = manager.dialog_data.get("category")
    session: AsyncSession = manager.middleware_data["session"]
    current_lang = get_lang_code(manager.dialog_data.get("language", "uz"))

    if movie_type == "series":
        season = manager.dialog_data.get("season")
        eps = await _get_series_actions(session, category).get_series(code)
        existing_ep = next(
            (e for e in eps if e.season == season and e.series == num), None
        )
        if existing_ep:
            manager.dialog_data["is_adding_track"] = True
    elif movie_type == "mini_series":
        eps = await _get_mini_actions(session, category).get_mini_series(code)
        existing_ep = next((e for e in eps if e.series == num), None)
        if existing_ep:
            manager.dialog_data["is_adding_track"] = True

    manager.dialog_data["series"] = num
    await manager.switch_to(AddMovieWizardSG.input_file)


async def on_quality_selected(
    c: CallbackQuery, widget: Any, manager: DialogManager, item_id: str
):
    manager.dialog_data["input_quality"] = item_id
    await manager.switch_to(AddMovieWizardSG.input_caption)


async def on_skip_quality(c: CallbackQuery, widget: Any, manager: DialogManager):
    manager.dialog_data["input_quality"] = None
    await manager.switch_to(AddMovieWizardSG.input_caption)


async def on_file_input(m: Message, widget: Any, manager: DialogManager):
    # ✅ Yangi video keldi — eski files keshini tozalab tashlaymiz
    manager.dialog_data.pop("files", None)

    if m.video:
        manager.dialog_data["file_id"] = m.video.file_id
        manager.dialog_data["format"] = (
            f"{m.video.height}p" if m.video.height else "Original"
        )
    elif m.document:
        manager.dialog_data["file_id"] = m.document.file_id
    else:
        await m.answer(str(_("❌ Video yoki fayl yuboring!")))
        return
    await manager.switch_to(AddMovieWizardSG.select_input_quality)


async def on_caption_input(m: Message, widget: Any, manager: DialogManager):
    lang = manager.dialog_data.get("language")
    input_text = m.html_text if m.caption else m.text

    if lang:
        lang_id = get_lang_code(lang)
        current_caption = manager.dialog_data.get("caption")
        if not isinstance(current_caption, dict):
            current_caption = {"uz": str(current_caption)} if current_caption else {}
        current_caption[lang_id] = input_text
        manager.dialog_data["caption"] = current_caption
    else:
        manager.dialog_data["caption"] = input_text

    await manager.switch_to(AddMovieWizardSG.input_thumbnail)


async def on_skip_caption(c: CallbackQuery, widget: Any, manager: DialogManager):
    manager.dialog_data["caption"] = None
    await manager.switch_to(AddMovieWizardSG.input_thumbnail)


async def _trigger_admin_preview(manager: DialogManager):
    manager.show_mode = ShowMode.SEND


async def on_thumbnail_input(m: Message, widget: Any, manager: DialogManager):
    if m.photo:
        manager.dialog_data["thumbnail_file_id"] = m.photo[-1].file_id
    elif (
        m.document
        and m.document.mime_type
        and m.document.mime_type.startswith("image/")
    ):
        manager.dialog_data["thumbnail_file_id"] = m.document.file_id
    else:
        await m.answer(str(_("❌ Rasm yuboring (JPG, PNG)!")))
    is_adding = manager.dialog_data.get("is_adding_track", False)
    movie_type = manager.dialog_data.get("movie_type")

    if is_adding or movie_type in ["series", "mini_series"]:
        await _trigger_admin_preview(manager)
        await manager.switch_to(AddMovieWizardSG.confirm)
    else:
        await manager.switch_to(AddMovieWizardSG.input_language)


async def on_skip_thumbnail(c: CallbackQuery, widget: Any, manager: DialogManager):
    manager.dialog_data.pop("thumbnail_file_id", None)
    is_adding = manager.dialog_data.get("is_adding_track", False)
    movie_type = manager.dialog_data.get("movie_type")

    if is_adding or movie_type in ["series", "mini_series"]:
        await _trigger_admin_preview(manager)
        await manager.switch_to(AddMovieWizardSG.confirm)
    else:
        await manager.switch_to(AddMovieWizardSG.input_language)


async def _handle_language_chosen(manager: DialogManager, lang_value: str):
    normalized_lang = lang_value.strip().lower()
    for l in LANGUAGES:
        if (
            normalized_lang == l["id"]
            or normalized_lang == l["label"].lower()
            or l["flag"] in normalized_lang
        ):
            normalized_lang = l["id"]
            break

    manager.dialog_data["language"] = normalized_lang
    manager.dialog_data.pop("lang_mode", None)

    if manager.dialog_data.get("editing_field") == "e_language":
        manager.dialog_data.pop("editing_field", None)
        saved = manager.dialog_data.pop("_saved_existing_langs", None)
        if saved is not None:
            manager.dialog_data["existing_langs"] = saved
        await _trigger_admin_preview(manager)
        await manager.switch_to(AddMovieWizardSG.confirm)
        return

    movie_type = manager.dialog_data.get("movie_type")
    is_adding = manager.dialog_data.get("is_adding_track", False)

    if movie_type == "feature_film" and not is_adding:
        if "genres" not in manager.dialog_data:
            manager.dialog_data["genres"] = []
        await manager.switch_to(AddMovieWizardSG.select_genres)
    elif movie_type == "series" and not is_adding:
        await manager.switch_to(AddMovieWizardSG.input_season_number)
    elif movie_type == "mini_series" and not is_adding:
        await manager.switch_to(AddMovieWizardSG.input_series_number)
    elif manager.dialog_data.get("name"):
        if movie_type == "series":
            await manager.switch_to(AddMovieWizardSG.input_season_number)
        elif movie_type == "mini_series":
            await manager.switch_to(AddMovieWizardSG.input_series_number)
        else:
            await manager.switch_to(AddMovieWizardSG.input_file)
    else:
        await manager.switch_to(AddMovieWizardSG.input_name)


async def on_language_input(m: Message, widget: Any, manager: DialogManager):
    await _handle_language_chosen(manager, m.text)


async def on_language_selected(
    c: CallbackQuery, widget: Any, manager: DialogManager, item_id: str
):
    await _handle_language_chosen(manager, item_id)


async def on_skip_language(c: CallbackQuery, widget: Any, manager: DialogManager):
    await _handle_language_chosen(manager, "uz")


async def on_genre_toggle(
    c: CallbackQuery, widget: Any, manager: DialogManager, item_id: str = None
):
    if widget.widget_id == "confirm_genres":
        if manager.dialog_data.get("editing_field") == "e_genres":
            manager.dialog_data.pop("editing_field", None)
            await _trigger_admin_preview(manager)
            await manager.switch_to(AddMovieWizardSG.confirm)
            return

        m_type = manager.dialog_data.get("movie_type")
        lang_set = bool(manager.dialog_data.get("language"))
        if m_type == "series":
            await manager.switch_to(
                AddMovieWizardSG.input_season_number
                if lang_set
                else AddMovieWizardSG.input_language
            )
        elif m_type == "mini_series":
            await manager.switch_to(
                AddMovieWizardSG.input_series_number
                if lang_set
                else AddMovieWizardSG.input_language
            )
        else:
            await _trigger_admin_preview(manager)
            await manager.switch_to(AddMovieWizardSG.confirm)
        return

    if not item_id:
        return
    selected = list(manager.dialog_data.get("genres", []))
    if item_id in selected:
        selected.remove(item_id)
    else:
        selected.append(item_id)
    manager.dialog_data["genres"] = selected
    await c.answer()


# ─────────────────────────────────────────────
#  Auto Posting Preview Handlers
# ─────────────────────────────────────────────


async def on_post_preview_click(c: CallbackQuery, widget: Any, manager: DialogManager):
    config = load_config()
    tmdb = TMDBService(config.tmdb_api_key)

    movie_name = manager.dialog_data.get("name")
    if isinstance(movie_name, dict):
        # Prefer UZ name, then RU, then first available
        movie_name = (
            movie_name.get("uz")
            or movie_name.get("ru")
            or next(iter(movie_name.values()))
        )

    session = manager.middleware_data["session"]
    all_langs = await get_all_languages_for_code(
        session, manager.dialog_data.get("code")
    )
    # Add current language if not in list
    curr_lang = manager.dialog_data.get("language")
    if curr_lang and curr_lang not in all_langs:
        all_langs.append(curr_lang)
    manager.dialog_data["all_movie_langs"] = all_langs

    # Always Refresh caption and images to sync with possible wizard edits
    # UNLESS manual override is set
    if manager.dialog_data.get("poster_manual_override"):
        await manager.switch_to(AddMovieWizardSG.post_preview)
        return

    tmdb_result = await tmdb.parse_movie(movie_name)
    if tmdb_result:
        manager.dialog_data["tmdb_data"] = tmdb_result["data"]
        manager.dialog_data["tmdb_id"] = tmdb_result["tmdb_id"]

        # Fetch all backdrops (horizontal)
        images = tmdb.get_all_backdrops(tmdb_result["data"])
        manager.dialog_data["all_posters"] = images
        # Only reset index if images changed or not set
        if manager.dialog_data.get("post_image") not in images:
            manager.dialog_data["poster_index"] = 0
            if images:
                manager.dialog_data["post_image"] = images[0]
            else:
                manager.dialog_data["post_image"] = tmdb_result["preview"]

        # Use current target language for initial caption
        target_lang = manager.dialog_data.get("post_target_lang", "uz")

        # Get localized title
        movie_name_data = manager.dialog_data.get("name", {})
        if isinstance(movie_name_data, dict):
            title_to_use = movie_name_data.get(target_lang)
            if not title_to_use:
                tmdb_title = await tmdb.get_localized_title(
                    tmdb_result["tmdb_id"], target_lang
                )
                title_to_use = tmdb_title or movie_name_data.get("uz") or movie_name
        else:
            title_to_use = movie_name_data or movie_name

        data_for_caption = tmdb_result["data"].copy()
        data_for_caption["title"] = title_to_use

        manager.dialog_data["post_caption"] = tmdb.format_caption(
            data_for_caption,
            code=manager.dialog_data.get("code"),
            genres_str=get_post_hashtags(
                manager.dialog_data.get("genres", []), target_lang=target_lang
            ),
            quality=manager.dialog_data.get("input_quality"),
            all_langs=all_langs,
            target_lang=target_lang,
        )
    else:
        # Fallback if not found
        manager.dialog_data["all_posters"] = []
        manager.dialog_data["poster_index"] = 0
        manager.dialog_data["post_image"] = manager.dialog_data.get("thumbnail_file_id")
        manager.dialog_data["post_caption"] = (
            f"🎬 <b>NOMI:</b> {movie_name}\n\n💾 <b>KODI:</b> {manager.dialog_data.get('code')}"
        )

    await manager.switch_to(AddMovieWizardSG.post_preview)


async def on_prev_poster(c: CallbackQuery, widget: Any, manager: DialogManager):
    images = manager.dialog_data.get("all_posters", [])
    if not images:
        return

    current_idx = manager.dialog_data.get("poster_index", 0)
    new_idx = (current_idx - 1) % len(images)
    manager.dialog_data["poster_index"] = new_idx
    manager.dialog_data["post_image"] = images[new_idx]
    await c.answer(
        str(_("🖼 Oldingi rasm ({idx}/{total})")).format(
            idx=new_idx + 1, total=len(images)
        )
    )


async def on_next_poster(c: CallbackQuery, widget: Any, manager: DialogManager):
    images = manager.dialog_data.get("all_posters", [])
    if not images:
        await c.answer(str(_("❌ Rasmlar topilmadi")))
        return

    current_idx = manager.dialog_data.get("poster_index", 0)
    new_idx = (current_idx + 1) % len(images)
    manager.dialog_data["poster_index"] = new_idx
    manager.dialog_data["post_image"] = images[new_idx]
    await c.answer(
        str(_("🖼 Keyingi rasm ({idx}/{total})")).format(
            idx=new_idx + 1, total=len(images)
        )
    )


async def on_post_lang_change(
    c: CallbackQuery, widget: Any, manager: DialogManager, item_id: str
):
    manager.dialog_data["post_target_lang"] = item_id
    await on_refresh_post(c, widget, manager)


def get_post_hashtags(genres, target_lang="uz"):
    if not genres:
        return ""
    # Map from any source genre name to the target language name
    translations = {
        "uz": {
            "Боевик": "Jangari",
            "Action": "Jangari",
            "Jangari": "Jangari",
            "Драма": "Drama",
            "Drama": "Drama",
            "Комедия": "Komediya",
            "Comedy": "Komediya",
            "Komediya": "Komediya",
            "Триллер": "Triller",
            "Thriller": "Triller",
            "Triller": "Triller",
            "Ужасы": "Qorqinchli",
            "Horror": "Qorqinchli",
            "Qorqinchli": "Qorqinchli",
            "Фантастика": "Fantastika",
            "Science Fiction": "Fantastika",
            "Fantastika": "Fantastika",
            "Фэнтези": "Fentezi",
            "Fantasy": "Fentezi",
            "Fentezi": "Fentezi",
            "Мелодрама": "Melodrama",
            "Romance": "Romantika",
            "Романтика": "Romantika",
            "#Романтика": "Romantika",
            "Romantika": "Romantika",
            "Melodrama": "Melodrama",
            "Детектив": "Detektiv",
            "Mystery": "Detektiv",
            "Detektiv": "Detektiv",
            "Приключения": "Sarguzasht",
            "Adventure": "Sarguzasht",
            "Sarguzasht": "Sarguzasht",
            "Семейный": "Oilaviy",
            "Family": "Oilaviy",
            "Oilaviy": "Oilaviy",
            "Мультфильм": "Multfilm",
            "Animation": "Multfilm",
            "Multfilm": "Multfilm",
            "Исторический": "Tarixiy",
            "History": "Tarixiy",
            "Tarixiy": "Tarixiy",
            "Документальный": "Hujjatli",
            "Documentary": "Hujjatli",
            "Hujjatli": "Hujjatli",
            "Военный": "Harbiy",
            "War": "Harbiy",
            "Harbiy": "Harbiy",
            "Криминал": "Kriminal",
            "Crime": "Kriminal",
            "Kriminal": "Kriminal",
            "Биография": "Biografiya",
            "Biography": "Biografiya",
            "Biografiya": "Biografiya",
            "Anime": "Anime",
            "Аниме": "Anime",
            "Psychological": "Psixologik",
            "Психологический": "Psixologik",
            "Psixologik": "Psixologik",
            "Short": "Qisqa metrajli",
            "Короткометражка": "Qisqa metrajli",
            "Musical": "Myuzikl",
            "Мюзикл": "Myuzikl",
            "Western": "Vestern",
            "Вестерн": "Vestern",
            "TV Movie": "Televizion film",
            "Телевизионный фильм": "Televizion film",
        },
        "ru": {
            "Action": "Боевик",
            "Jangari": "Боевик",
            "Боевик": "Боевик",
            "Drama": "Драма",
            "Драма": "Драма",
            "Comedy": "Комедия",
            "Komediya": "Комедия",
            "Комедия": "Комедия",
            "Thriller": "Триллер",
            "Triller": "Триллер",
            "Триллер": "Триллер",
            "Horror": "Ужасы",
            "Qorqinchli": "Ужасы",
            "Ужасы": "Ужасы",
            "Science Fiction": "Фантастика",
            "Fantastika": "Фантастика",
            "Фантастика": "Фантастика",
            "Fantasy": "Фэнтези",
            "Fentezi": "Фэнтези",
            "Фэнтези": "Фэнтези",
            "Romance": "Мелодрама",
            "Melodrama": "Мелодрама",
            "Романтика": "Мелодрама",
            "#Романтика": "Мелодрама",
            "Мелодрама": "Мелодрама",
            "Mystery": "Детектив",
            "Detektiv": "Детектив",
            "Детектив": "Детектив",
            "Adventure": "Приключения",
            "Sarguzasht": "Приключения",
            "Приключения": "Приключения",
            "Family": "Семейный",
            "Oilaviy": "Семейный",
            "Семейный": "Семейный",
            "Animation": "Мультфильм",
            "Multfilm": "Мультфильм",
            "Мультфильм": "Мультфильм",
            "History": "Исторический",
            "Tarixiy": "Исторический",
            "Исторический": "Исторический",
            "Documentary": "Документальный",
            "Hujjatli": "Документальный",
            "Документальный": "Документальный",
            "War": "Военный",
            "Harbiy": "Военный",
            "Военный": "Военный",
            "Crime": "Криминал",
            "Kriminal": "Криминал",
            "Криминал": "Криминал",
            "Biography": "Биография",
            "Biografiya": "Биография",
            "Биография": "Биография",
            "Anime": "Аниме",
            "Аниме": "Аниме",
            "Psychological": "Психологический",
            "Psixologik": "Психологический",
            "Психологический": "Психологический",
            "Short": "Короткометражка",
            "Qisqa metrajli": "Короткометражка",
            "Musical": "Мюзикл",
            "Myuzikl": "Мюзикл",
            "Western": "Вестерн",
            "Vestern": "Вестерн",
            "TV Movie": "Телевизионный фильм",
            "Televizion film": "Телевизионный фильм",
        },
        "en": {
            "Боевик": "Action",
            "Jangari": "Action",
            "Action": "Action",
            "Драма": "Drama",
            "Drama": "Drama",
            "Комедия": "Comedy",
            "Komediya": "Comedy",
            "Comedy": "Comedy",
            "Триллер": "Thriller",
            "Triller": "Thriller",
            "Thriller": "Thriller",
            "Ужасы": "Horror",
            "Qorqinchli": "Horror",
            "Horror": "Horror",
            "Фантастика": "Sci-Fi",
            "Fantastika": "Sci-Fi",
            "Sci-Fi": "Sci-Fi",
            "Фэнтези": "Fantasy",
            "Fentezi": "Fantasy",
            "Fantasy": "Fantasy",
            "Мелодрама": "Romance",
            "Melodrama": "Romance",
            "Romance": "Romance",
            "Детектив": "Mystery",
            "Detektiv": "Mystery",
            "Mystery": "Mystery",
            "Приключения": "Adventure",
            "Sarguzasht": "Adventure",
            "Adventure": "Adventure",
            "Семейный": "Family",
            "Oilaviy": "Family",
            "Family": "Family",
            "Мультфильм": "Animation",
            "Multfilm": "Animation",
            "Animation": "Animation",
            "Исторический": "History",
            "Tarixiy": "History",
            "History": "History",
            "Документальный": "Documentary",
            "Hujjatli": "Documentary",
            "Documentary": "Documentary",
            "Военный": "War",
            "Harbiy": "War",
            "War": "War",
            "Криминал": "Crime",
            "Kriminal": "Crime",
            "Crime": "Crime",
            "Биография": "Biography",
            "Biografiya": "Biography",
            "Biography": "Biography",
            "Аниме": "Anime",
            "Anime": "Anime",
            "Психологический": "Psychological",
            "Psixologik": "Psychological",
            "Psychological": "Psychological",
            "Короткометражка": "Short",
            "Qisqa metrajli": "Short",
            "Мюзикл": "Musical",
            "Myuzikl": "Musical",
            "Вестерн": "Western",
            "Vestern": "Western",
            "Телевизионный фильм": "TV Movie",
            "Televizion film": "TV Movie",
        },
    }

    lang_map = translations.get(target_lang, translations["uz"])
    return " ".join([f"{lang_map.get(g, g.replace(' ', ''))}" for g in genres])


def get_language_display_text(lang_id):
    if not lang_id:
        return "N/A"
    for l in LANGUAGES:
        if l["id"] == lang_id:
            return f"{l['label']} {l['flag']}"
    return lang_id


async def on_refresh_post(c: CallbackQuery, widget: Any, manager: DialogManager):
    config = load_config()
    tmdb = TMDBService(config.tmdb_api_key)
    tmdb_data = manager.dialog_data.get("tmdb_data", {})

    movie_name_data = manager.dialog_data.get("name", {})
    target_lang = manager.dialog_data.get("post_target_lang", "uz")

    # Get localized title from the name dictionary if it is a dict
    if isinstance(movie_name_data, dict):
        title_to_use = movie_name_data.get(target_lang)
        if not title_to_use:
            # Try to fetch from TMDB if tmdb_id is available and target_lang is not UZ
            tmdb_id = manager.dialog_data.get("tmdb_id")
            if tmdb_id:
                # Map internal lang codes to TMDB lang codes
                tmdb_lang_map = {"uz": "uz-UZ", "ru": "ru-RU", "en": "en-US"}
                tmdb_title = await tmdb.get_localized_title(
                    tmdb_id, tmdb_lang_map.get(target_lang, "en-US")
                )
                if tmdb_title:
                    title_to_use = tmdb_title
                    # Save it to name_data for future use
                    movie_name_data[target_lang] = tmdb_title

            if not title_to_use:
                # Final fallback sequence
                title_to_use = (
                    movie_name_data.get("uz")
                    or movie_name_data.get("ru")
                    or next(iter(movie_name_data.values()), "N/A")
                )
    else:
        title_to_use = movie_name_data or "N/A"

    # Copy tmdb_data and override title with our localized version
    data_for_caption = (tmdb_data or {}).copy()
    data_for_caption["title"] = title_to_use

    manager.dialog_data["post_caption"] = tmdb.format_caption(
        data_for_caption,
        code=manager.dialog_data.get("code"),
        genres_str=get_post_hashtags(
            manager.dialog_data.get("genres", []), target_lang=target_lang
        ),
        quality=manager.dialog_data.get("input_quality"),
        all_langs=manager.dialog_data.get("all_movie_langs"),
        target_lang=target_lang,
    )
    await c.answer(str(_("✅ Post yangilandi")))


async def on_post_publish(c: CallbackQuery, widget: Any, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    post_actions = PostChannelActions(session)
    channels = await post_actions.get_active_post_channels()

    image = manager.dialog_data.get("post_image")
    caption = manager.dialog_data.get("post_caption")

    sent_count = 0
    for channel in channels:
        try:
            if image:
                if isinstance(image, str) and image.startswith("http"):
                    await c.bot.send_photo(
                        channel.channel_id,
                        photo=image,
                        caption=caption,
                        parse_mode="HTML",
                    )
                else:
                    await c.bot.send_photo(
                        channel.channel_id,
                        photo=image,
                        caption=caption,
                        parse_mode="HTML",
                    )
            else:
                await c.bot.send_message(
                    channel.channel_id, text=caption, parse_mode="HTML"
                )
            sent_count += 1
        except Exception as e:
            logger.error(f"Post publishing error for channel {channel.channel_id}: {e}")

    await c.answer(
        str(_("✅ Post {count} ta kanalga yuborildi.")).format(count=sent_count),
        show_alert=True,
    )


async def on_edit_post_image_input(m: Message, widget: Any, manager: DialogManager):
    if m.photo:
        manager.dialog_data["post_image"] = m.photo[-1].file_id
    elif m.text and m.text.startswith("http"):
        manager.dialog_data["post_image"] = m.text
    else:
        await m.answer(str(_("❌ Rasm yuboring yoki rasm linkini yuboring.")))
        return
    await manager.switch_to(AddMovieWizardSG.post_preview)


async def on_edit_post_caption_input(m: Message, widget: Any, manager: DialogManager):
    manager.dialog_data["post_caption"] = m.html_text or m.text
    await manager.switch_to(AddMovieWizardSG.post_preview)


async def on_edit_post_search_name_input(m: Message, widget: Any, manager: DialogManager):
    config = load_config()
    tmdb = TMDBService(config.tmdb_api_key)
    new_name = m.text

    tmdb_result = await tmdb.parse_movie(new_name)
    if tmdb_result:
        manager.dialog_data["tmdb_data"] = tmdb_result["data"]
        manager.dialog_data["tmdb_id"] = tmdb_result["tmdb_id"]
        manager.dialog_data["poster_manual_override"] = True

        images = tmdb.get_all_backdrops(tmdb_result["data"])
        manager.dialog_data["all_posters"] = images
        manager.dialog_data["poster_index"] = 0
        if images:
            manager.dialog_data["post_image"] = images[0]
        else:
            manager.dialog_data["post_image"] = tmdb_result["preview"]

        target_lang = manager.dialog_data.get("post_target_lang", "uz")
        all_langs = manager.dialog_data.get("all_movie_langs", [])

        # Localized title
        movie_name_data = manager.dialog_data.get("name", {})
        if isinstance(movie_name_data, dict):
            title_to_use = movie_name_data.get(target_lang)
            if not title_to_use:
                tmdb_title = await tmdb.get_localized_title(
                    tmdb_result["tmdb_id"], target_lang
                )
                title_to_use = tmdb_title or next(iter(movie_name_data.values()), new_name)
        else:
            title_to_use = movie_name_data or new_name

        data_for_caption = tmdb_result["data"].copy()
        data_for_caption["title"] = title_to_use

        manager.dialog_data["post_caption"] = tmdb.format_caption(
            data_for_caption,
            code=manager.dialog_data.get("code"),
            genres_str=get_post_hashtags(
                manager.dialog_data.get("genres", []), target_lang=target_lang
            ),
            quality=manager.dialog_data.get("input_quality"),
            all_langs=all_langs,
            target_lang=target_lang,
        )
        await m.answer(str(_("✅ Yangi ma'lumotlar topildi!")))
    else:
        await m.answer(str(_("❌ Bunday nomli film topilmadi. Qayta urinib ko'ring.")))
        return

    await manager.switch_to(AddMovieWizardSG.post_preview)


async def get_post_preview_data(dialog_manager: DialogManager, **kwargs):
    image = dialog_manager.dialog_data.get("post_image")
    caption = dialog_manager.dialog_data.get("post_caption")

    media = None
    if image:
        if isinstance(image, str) and image.startswith("http"):
            media = MediaAttachment(ContentType.PHOTO, url=image)
        else:
            media = MediaAttachment(ContentType.PHOTO, file_id=MediaId(image))

    target_lang = dialog_manager.dialog_data.get("post_target_lang", "uz")
    images = dialog_manager.dialog_data.get("all_posters", [])
    current_idx = dialog_manager.dialog_data.get("poster_index", 0)
    total = len(images)

    return {
        "media": media,
        "caption": caption or "No caption",
        "lang_select_label": str(_("🌍 Tilni almashtirish")),
        "back_label": str(_("🔙 Ortga")),
        "img_edit_label": str(_("🖼 Rasmni o'zgartirish")),
        "cap_edit_label": str(_("📝 Matnni o'zgartirish")),
        "publish_label": str(_("🚀 Postni chiqarish")),
        "refresh_label": str(_("🔄 Yangilash")),
        "next_label": "▶️",
        "prev_label": "◀️",
        "counter": f"{current_idx + 1}/{total}" if total > 0 else "0/0",
        "has_next": total > 1 and current_idx < total - 1,
        "has_prev": total > 1 and current_idx > 0,
        "img_prompt": str(_("🖼 Yangi rasm yuboring yoki rasm linkini yuboring:")),
        "cap_prompt": str(_("📝 Yangi post matnini yuboring:")),
        "search_name_prompt": str(_("🔍 Qidiruv uchun yangi nom kiriting:")),
        "btn_edit_search_name": str(_("🔎 Qidiruv nomini o'zgartirish")),
    }


# ─────────────────────────────────────────────
#  ASOSIY: on_confirm
# ─────────────────────────────────────────────


async def on_confirm(c: CallbackQuery, widget: Any, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    data = manager.dialog_data
    movie_type = data.get("movie_type")
    category = data.get("category")

    try:
        file_id = data.get("file_id")
        if not file_id:
            await c.message.answer(
                str(_("❌ Video fayl topilmadi! Qaytadan video yuboring."))
            )
            return

        # ✅ Har doim eski "files" keshini o'chirib, transcoder ishlatamiz
        data.pop("files", None)

        from src.app.services.tasks import process_video_task

        status_msg = await c.message.answer(
            str(lazy_gettext("⏳ Video tayyorlanmoqda (Local Worker)..."))
        )

        admin_locale = manager.middleware_data.get("i18n").current_locale

        # Auto-generate post data if missing (for auto-posting feature)
        if not data.get("post_caption"):
            config = load_config()
            tmdb = TMDBService(config.tmdb_api_key)
            movie_name = data.get("name")
            if isinstance(movie_name, dict):
                movie_name = (
                    movie_name.get("uz")
                    or movie_name.get("ru")
                    or next(iter(movie_name.values()))
                )

            tmdb_result = await tmdb.parse_movie(movie_name)
            if tmdb_result:
                data["post_image"] = tmdb_result["preview"]
                data["post_caption"] = tmdb.format_caption(
                    tmdb_result["data"],
                    code=data.get("code"),
                    genres_str=get_post_hashtags(data.get("genres", [])),
                    lang_str=get_language_display_text(data.get("language")),
                    quality=data.get("input_quality"),
                )
            else:
                data["post_image"] = data.get("thumbnail_file_id")
                data["post_caption"] = (
                    f"🎬 <b>Nomi:</b> {movie_name}\n\n💾 <b>KODI:</b> {data.get('code')}"
                )

        task_data = {
            "admin_id": c.from_user.id,
            "status_msg_id": status_msg.message_id,
            "admin_locale": admin_locale,
            "file_id": file_id,
            "thumbnail_file_id": data.get("thumbnail_file_id"),
            "category": category,
            "movie_type": movie_type,
            "code": data.get("code"),
            "name": data.get("name"),
            "caption": data.get("caption"),
            "genres": data.get("genres"),
            "format": data.get("format"),
            "language": data.get("language"),
            "input_quality": data.get("input_quality"),
            # Ensure is_adding_track is passed correctly from dialog_data
            "is_adding_track": data.get("is_adding_track", False)
            or data.get("exists", False),
            "season": data.get("season"),
            "series": data.get("series"),
        }

        process_video_task.delay(task_data)

        await c.message.answer(
            str(
                _(
                    "🚀 Transkodlash vazifasi navbatga qo'shildi. Jarayon tugagach sizga xabar yuboriladi."
                )
            )
        )
        await manager.switch_to(AddMovieWizardSG.success)
        return

    except Exception as e:
        logger.error(f"on_confirm critical error: {e}", exc_info=True)
        await c.message.answer(
            str(_("❌ Xato: {error}")).format(error=html.escape(str(e)))
        )


async def _save_film(
    session, movie_type, data, is_adding, lang_id, genres, files, thumbnail_id=None
):
    if movie_type == "feature_film":
        actions = FeatureFilmsActions(session)
        if is_adding:
            await actions.add_language_track(
                film_code=data["code"],
                language=lang_id,
                caption=data.get("caption"),
                files=files,
                name=data.get("name"),
                thumbnail_file_id=thumbnail_id,
            )
        else:
            await actions.add_feature_film(
                film_code=data["code"],
                film_name=data["name"],
                caption=data.get("caption"),
                genres=genres,
                language=lang_id,
                files=files,
                thumbnail_file_id=thumbnail_id,
            )
    elif movie_type == "series":
        actions = SeriesActions(session)
        if is_adding:
            await actions.add_language_track(
                series_code=data["code"],
                season=data["season"],
                series_num=data["series"],
                language=lang_id,
                caption=data.get("caption"),
                files=files,
                name=data.get("name"),
                thumbnail_file_id=thumbnail_id,
            )
        else:
            await actions.add_series(
                series_code=data["code"],
                series_name=data["name"],
                series_num=data["series"],
                season=data["season"],
                caption=data.get("caption"),
                genres=genres,
                language=lang_id,
                files=files,
                thumbnail_file_id=thumbnail_id,
            )
    elif movie_type == "mini_series":
        actions = MiniSeriesActions(session)
        if is_adding:
            await actions.add_language_track(
                mini_series_code=data["code"],
                series_num=data["series"],
                language=lang_id,
                caption=data.get("caption"),
                files=files,
                name=data.get("name"),
                thumbnail_file_id=thumbnail_id,
            )
        else:
            await actions.add_mini_series(
                mini_series_code=data["code"],
                mini_series_name=data["name"],
                series=data["series"],
                caption=data.get("caption"),
                genres=genres,
                language=lang_id,
                files=files,
                thumbnail_file_id=thumbnail_id,
            )


async def _save_multi_film(
    session, movie_type, data, is_adding, lang_id, genres, files, thumbnail_id=None
):
    if movie_type == "feature_film":
        actions = MultiFilmFeatureActions(session)
        if is_adding:
            await actions.add_language_track(
                film_code=data["code"],
                language=lang_id,
                caption=data.get("caption"),
                files=files,
                name=data.get("name"),
                thumbnail_file_id=thumbnail_id,
            )
        else:
            await actions.add_feature_film(
                film_code=data["code"],
                film_name=data["name"],
                caption=data.get("caption"),
                genres=genres,
                language=lang_id,
                files=files,
                thumbnail_file_id=thumbnail_id,
            )
    elif movie_type == "series":
        actions = MultiFilmSeriesActions(session)
        if is_adding:
            await actions.add_language_track(
                series_code=data["code"],
                season=data["season"],
                series_num=data["series"],
                language=lang_id,
                caption=data.get("caption"),
                files=files,
                name=data.get("name"),
                thumbnail_file_id=thumbnail_id,
            )
        else:
            await actions.add_series(
                series_code=data["code"],
                series_name=data["name"],
                series_num=data["series"],
                season=data["season"],
                caption=data.get("caption"),
                genres=genres,
                language=lang_id,
                files=files,
                thumbnail_file_id=thumbnail_id,
            )
    elif movie_type == "mini_series":
        actions = MultiFilmMiniSeriesActions(session)
        if is_adding:
            await actions.add_language_track(
                mini_series_code=data["code"],
                series_num=data["series"],
                language=lang_id,
                caption=data.get("caption"),
                files=files,
                name=data.get("name"),
                thumbnail_file_id=thumbnail_id,
            )
        else:
            await actions.add_mini_series(
                mini_series_code=data["code"],
                mini_series_name=data["name"],
                series=data["series"],
                caption=data.get("caption"),
                genres=genres,
                language=lang_id,
                files=files,
                thumbnail_file_id=thumbnail_id,
            )


async def _save_anime(
    session, movie_type, data, is_adding, lang_id, genres, files, thumbnail_id=None
):
    if movie_type == "feature_film":
        actions = AnimeFeatureActions(session)
        if is_adding:
            await actions.add_language_track(
                film_code=data["code"],
                language=lang_id,
                caption=data.get("caption"),
                files=files,
                name=data.get("name"),
                thumbnail_file_id=thumbnail_id,
            )
        else:
            await actions.add_feature_film(
                film_code=data["code"],
                film_name=data["name"],
                caption=data.get("caption"),
                genres=genres,
                language=lang_id,
                files=files,
                thumbnail_file_id=thumbnail_id,
            )
    elif movie_type == "series":
        actions = AnimeSeriesActions(session)
        if is_adding:
            await actions.add_language_track(
                series_code=data["code"],
                season=data["season"],
                series_num=data["series"],
                language=lang_id,
                caption=data.get("caption"),
                files=files,
                name=data.get("name"),
                thumbnail_file_id=thumbnail_id,
            )
        else:
            await actions.add_series(
                series_code=data["code"],
                series_name=data["name"],
                series_num=data["series"],
                season=data["season"],
                caption=data.get("caption"),
                genres=genres,
                language=lang_id,
                files=files,
                thumbnail_file_id=thumbnail_id,
            )
    elif movie_type == "mini_series":
        actions = AnimeMiniSeriesActions(session)
        if is_adding:
            await actions.add_language_track(
                mini_series_code=data["code"],
                series_num=data["series"],
                language=lang_id,
                caption=data.get("caption"),
                files=files,
                name=data.get("name"),
                thumbnail_file_id=thumbnail_id,
            )
        else:
            await actions.add_mini_series(
                mini_series_code=data["code"],
                mini_series_name=data["name"],
                series=data["series"],
                caption=data.get("caption"),
                genres=genres,
                language=lang_id,
                files=files,
                thumbnail_file_id=thumbnail_id,
            )


async def on_toggle_preview(c: CallbackQuery, widget: Any, manager: DialogManager):
    current = manager.dialog_data.get("preview_mode", "video")
    manager.dialog_data["preview_mode"] = "thumbnail" if current == "video" else "video"
    await c.answer()


async def on_edit_click(c: CallbackQuery, widget: Any, manager: DialogManager):
    await _trigger_admin_preview(manager)
    await manager.switch_to(AddMovieWizardSG.edit_menu)


async def on_edit_language(c: CallbackQuery, widget: Any, manager: DialogManager):
    manager.dialog_data["editing_field"] = "e_language"
    cur_lang = get_lang_code(manager.dialog_data.get("language", "uz"))
    manager.dialog_data["_saved_existing_langs"] = manager.dialog_data.get(
        "existing_langs", []
    )
    manager.dialog_data["existing_langs"] = [cur_lang]
    manager.dialog_data["lang_mode"] = "new"
    await manager.switch_to(AddMovieWizardSG.input_language)


async def on_edit_field_selected(
    c: CallbackQuery, widget: Button, manager: DialogManager
):
    manager.dialog_data["editing_field"] = widget.widget_id
    if widget.widget_id == "e_genres":
        await manager.switch_to(AddMovieWizardSG.select_genres)
    else:
        await manager.switch_to(AddMovieWizardSG.edit_field)


async def on_field_edit_input(m: Message, widget: Any, manager: DialogManager):
    field = manager.dialog_data.get("editing_field")
    session: AsyncSession = manager.middleware_data["session"]

    if field == "e_code":
        if not m.text.isdigit():
            await m.answer(str(_("❌ Faqat raqam!")))
            return
        new_code = int(m.text)
        ff = await FeatureFilmsActions(session).get_feature_film(new_code)
        s = await SeriesActions(session).get_series(new_code)
        ms = await MiniSeriesActions(session).get_mini_series(new_code)
        if ff or s or ms:
            await m.answer(str(_("⚠️ Bu kod band. Boshqa raqam kiriting!")))
            return
        manager.dialog_data["code"] = new_code

    elif field == "e_name":
        lang = manager.dialog_data.get("language")
        if lang:
            lang_id = get_lang_code(lang)
            current_name = manager.dialog_data.get("name")
            if not isinstance(current_name, dict):
                current_name = {"uz": str(current_name)} if current_name else {}
            current_name[lang_id] = m.text
            manager.dialog_data["name"] = current_name
        else:
            manager.dialog_data["name"] = m.text

    elif field == "e_caption":
        lang = manager.dialog_data.get("language")
        input_text = m.html_text if m.caption else m.text
        if lang:
            lang_id = get_lang_code(lang)
            current_caption = manager.dialog_data.get("caption")
            if not isinstance(current_caption, dict):
                current_caption = (
                    {"uz": str(current_caption)} if current_caption else {}
                )
            current_caption[lang_id] = input_text
            manager.dialog_data["caption"] = current_caption
        else:
            manager.dialog_data["caption"] = input_text

    elif field == "e_video" and (m.video or m.document):
        manager.dialog_data["file_id"] = (
            m.video.file_id if m.video else m.document.file_id
        )
        # ✅ Yangi video — eski files keshini o'chiramiz
        manager.dialog_data.pop("files", None)

    elif field == "e_thumbnail" and (m.photo or m.document):
        manager.dialog_data["thumbnail_file_id"] = (
            m.photo[-1].file_id if m.photo else m.document.file_id
        )

    elif field == "e_season" and m.text.isdigit():
        new_season = int(m.text)
        code = manager.dialog_data.get("code")
        category = manager.dialog_data.get("category")
        movie_type = manager.dialog_data.get("movie_type")
        if movie_type == "series":
            eps = await _get_series_actions(session, category).get_series(code)
            current_series = manager.dialog_data.get("series")
            if any(e.season == new_season and e.series == current_series for e in eps):
                await m.answer(
                    str(_("⚠️ Sezon {s}, qism {e} allaqachon mavjud!")).format(
                        s=new_season, e=current_series
                    )
                )
                return
        manager.dialog_data["season"] = new_season

    elif field == "e_series" and m.text.isdigit():
        new_series = int(m.text)
        code = manager.dialog_data.get("code")
        movie_type = manager.dialog_data.get("movie_type")
        category = manager.dialog_data.get("category")
        if movie_type == "series":
            season = manager.dialog_data.get("season")
            eps = await _get_series_actions(session, category).get_series(code)
            if any(e.season == season and e.series == new_series for e in eps):
                await m.answer(
                    str(_("⚠️ Sezon {s}, qism {e} allaqachon mavjud!")).format(
                        s=season, e=new_series
                    )
                )
                return
        elif movie_type == "mini_series":
            eps = await _get_mini_actions(session, category).get_mini_series(code)
            if any(e.series == new_series for e in eps):
                await m.answer(
                    str(_("⚠️ {n}-qism allaqachon mavjud!")).format(n=new_series)
                )
                return
        manager.dialog_data["series"] = new_series

    await _trigger_admin_preview(manager)
    await manager.switch_to(AddMovieWizardSG.confirm)


async def on_finish(c: CallbackQuery, widget: Any, manager: DialogManager):
    await manager.done()


async def on_add_more(c: CallbackQuery, widget: Any, manager: DialogManager):
    _reset_keys(
        manager.dialog_data,
        [
            "series",
            "season",
            "file_id",
            "files",
            "editing_field",
            "format",
            "is_adding_track",
            "existing_langs",
        ],
    )
    await c.answer()
    if manager.dialog_data.get("name"):
        m_type = manager.dialog_data.get("movie_type") or manager.dialog_data.get(
            "exist_type"
        )
        if m_type == "series":
            await manager.switch_to(AddMovieWizardSG.input_season_number)
        elif m_type == "mini_series":
            await manager.switch_to(AddMovieWizardSG.input_series_number)
        else:
            await manager.switch_to(AddMovieWizardSG.input_file)
    else:
        await manager.switch_to(AddMovieWizardSG.input_name)


async def on_back_to_type(c: CallbackQuery, widget: Any, manager: DialogManager):
    await manager.switch_to(AddMovieWizardSG.choose_category)


async def on_finish_to_admin(c: CallbackQuery, widget: Any, manager: DialogManager):
    await manager.done()


async def on_cancel_to_type(c: CallbackQuery, widget: Any, manager: DialogManager):
    await manager.switch_to(AddMovieWizardSG.choose_type)


# ─────────────────────────────────────────────
#  GETTERS
# ─────────────────────────────────────────────


async def get_genre_data(dialog_manager: DialogManager, **kwargs):
    from src.app.bot.common.genres import GENRES

    selected_genres = dialog_manager.dialog_data.get("genres", [])
    genre_list = []
    for g in GENRES:
        name = g["name"]
        checkmark = "✅ " if name in selected_genres else ""
        genre_list.append((name, f"{checkmark}{str(g['label'])}"))

    from src.app.bot.common.utils import format_multi_name

    return {
        "name": format_multi_name(dialog_manager.dialog_data.get("name")),
        "genres": genre_list,
        "selected_text": get_genre_display_text(selected_genres, lang="ru"),
    }


async def get_language_data(dialog_manager: DialogManager, **kwargs):
    all_langs = LANGUAGES
    raw_existing = dialog_manager.dialog_data.get("existing_langs", [])
    existing = set()
    for l in raw_existing:
        if l and l.strip():
            code = get_lang_code(l.strip())
            if code:
                existing.add(code)
    lang_mode = dialog_manager.dialog_data.get("lang_mode", "new")

    if lang_mode == "all":
        available_langs = all_langs
        prompt_text = _("🌍 <b>Qaysi tilda qo'shmoqchisiz?</b>")
    elif lang_mode == "existing":
        available_langs = [l for l in all_langs if l["id"] in existing] or all_langs
        prompt_text = _("🌍 <b>Qaysi tilda davom etasiz?</b>")
    else:
        available_langs = [l for l in all_langs if l["id"] not in existing]
        prompt_text = _("🌍 <b>Yangi til tanlang:</b>")

    uz_match = next((l for l in LANGUAGES if l["id"] == "uz"), None)
    lang_label = uz_match["label"] if uz_match else "O'zbekcha"

    return {
        "languages": available_langs,
        "language_mode_prompt": str(prompt_text),
        "lang_label": lang_label,
    }


async def get_category_selection_data(dialog_manager: DialogManager, **kwargs):
    return {
        "cat_film": _("CAT_MOVIES"),
        "cat_multi": _("CAT_CARTOONS"),
        "cat_anime": _("CAT_ANIME"),
    }


async def get_type_selection_data(dialog_manager: DialogManager, **kwargs):
    category = dialog_manager.dialog_data.get("category")
    if category == "cat_anime":
        return {
            "type_film": _("TYPE_ANIME_MOVIE"),
            "type_series": _("TYPE_ANIME_SERIES"),
            "type_mini": _("TYPE_ANIME_MINI_SERIES"),
        }
    elif category == "cat_multi":
        return {
            "type_film": _("TYPE_CARTOON_MOVIE"),
            "type_series": _("TYPE_CARTOON_SERIES"),
            "type_mini": _("TYPE_CARTOON_MINI_SERIES"),
        }
    return {
        "type_film": _("TYPE_MOVIE"),
        "type_series": _("TYPE_SERIES"),
        "type_mini": _("TYPE_MINI_SERIES"),
    }


async def get_quality_data(dialog_manager: DialogManager, **kwargs):
    return {
        "qualities": [
            ("1080p", str(_("1080p"))),
            ("720p", str(_("720p"))),
            ("480p", str(_("480p"))),
            ("360p", str(_("360p"))),
        ]
    }


async def get_type_specific_prompts(dialog_manager: DialogManager, **kwargs):
    category = dialog_manager.dialog_data.get("category")
    movie_type = dialog_manager.dialog_data.get("movie_type")

    cat_prefix = ""
    if category == "cat_anime":
        cat_prefix = _("anime-")
    elif category == "cat_multi":
        cat_prefix = _("mult-")

    target_film = _("film")
    target_series = _("serial")
    target_episode = _("qism")

    return {
        "name_prompt": str(
            _("📝 <b>{prefix}{target} nomini kiriting:</b>").format(
                prefix=cat_prefix,
                target=target_film if movie_type == "feature_film" else target_series,
            )
        ),
        "season_prompt": str(
            _("🔢 <b>{prefix}Sezon raqamini kiriting:</b>").format(prefix=cat_prefix)
        ),
        "series_prompt": str(
            _("🔢 <b>{prefix}Qism raqamini kiriting:</b>").format(prefix=cat_prefix)
        ),
        "file_prompt": str(
            _("📹 <b>{prefix}{target} video faylini yuboring:</b>").format(
                prefix=cat_prefix,
                target=target_film if movie_type == "feature_film" else target_episode,
            )
        ),
        "caption_prompt": str(
            _("📄 <b>{prefix}{target} tavsifini kiriting:</b>").format(
                prefix=cat_prefix,
                target=target_film if movie_type == "feature_film" else target_episode,
            )
        ),
        "format_prompt": str(_("💿 <b>Format kiriting (masalan: HD, 4K):</b>")),
        "language_prompt": str(_("🌍 <b>Til kiriting:</b>")),
    }


async def get_edit_data(dialog_manager: DialogManager, **kwargs):
    field = dialog_manager.dialog_data.get("editing_field")
    prompts = {
        "e_code": _("🔢 Yangi kod (ID) kiriting:"),
        "e_name": _("📛 Yangi nomini kiriting:"),
        "e_caption": _("📄 Yangi tavsifni kiriting:"),
        "e_video": _("📹 Yangi video fayl yuboring:"),
        "e_thumbnail": _("🖼 Yangi muqova (thumbnail) yuboring:"),
        "e_format": _("💿 Yangi format kiriting (masalan: HD, 4K):"),
        "e_season": _("📅 Yangi sezon raqamini kiriting:"),
        "e_series": _("🔢 Yangi qism raqamini kiriting:"),
    }
    return {"prompt": prompts.get(field, _("O'zgartirish kiriting:"))}


async def get_quick_add_data(dialog_manager: DialogManager, **kwargs):
    d = dialog_manager.dialog_data
    movie_type = d.get("movie_type")
    e_type = d.get("exist_type")
    category = d.get("category")
    e_cat = d.get("exist_cat")

    can_continue = (category == e_cat) and (
        (movie_type == "series" and e_type == "series")
        or (movie_type == "mini_series" and e_type == "mini_series")
    )

    types = {
        "cat_film": {
            "feature_film": _("TYPE_MOVIE"),
            "series": _("TYPE_SERIES"),
            "mini_series": _("TYPE_MINI_SERIES"),
        },
        "cat_multi": {
            "feature_film": _("TYPE_CARTOON_MOVIE"),
            "series": _("TYPE_CARTOON_SERIES"),
            "mini_series": _("TYPE_CARTOON_MINI_SERIES"),
        },
        "cat_anime": {
            "feature_film": _("TYPE_ANIME_MOVIE"),
            "series": _("TYPE_ANIME_SERIES"),
            "mini_series": _("TYPE_ANIME_MINI_SERIES"),
        },
    }
    cats = {
        "cat_film": _("CAT_MOVIES"),
        "cat_multi": _("CAT_CARTOONS"),
        "cat_anime": _("CAT_ANIME"),
    }

    display_type = types.get(e_cat, {}).get(e_type, e_type or "")
    cat_label = cats.get(e_cat, e_cat or "")
    existing_langs = [l for l in d.get("existing_langs", []) if l]

    lang_info_list = []
    for l_id in existing_langs:
        match = next((l for l in LANGUAGES if l["id"] == l_id), None)
        if match:
            lang_info_list.append(f"{match['flag']} {match['label']}")
        else:
            norm_code = get_lang_code(l_id)
            match_norm = next((l for l in LANGUAGES if l["id"] == norm_code), None)
            if match_norm:
                lang_info_list.append(f"{match_norm['flag']} {match_norm['label']}")
            else:
                lang_info_list.append(f"❓ {l_id.upper()}")
    lang_info = " | ".join(lang_info_list) if lang_info_list else str(_("Yo'q"))

    from src.app.bot.common.utils import format_multi_name

    display_name = format_multi_name(d.get("name"))

    text = (
        f"━━━━━━━━━━━━━━━\n"
        f"<b>{_('SUM_CATEGORY')}</b> {cat_label}\n"
        f"<b>{_('SUM_TYPE')}</b> {display_type}\n"
        f"<b>{_('SUM_NAME')}</b> {display_name}\n"
        f"<b>{_('Mavjud tillar:')}</b> {lang_info}\n"
        f"━━━━━━━━━━━━━━━\n"
    )
    if can_continue:
        text += str(_("✅ Tur mos. Yangi qism qo'shishingiz mumkin."))
    else:
        text += str(
            _("⚠️ Bu kod boshqa turga tegishli. Faqat yangi til qo'shish mumkin.")
        )

    can_add_lang = len(existing_langs) < len(LANGUAGES)

    return {
        "display_type": display_type,
        "name": display_name,
        "can_continue": can_continue,
        "can_add_lang": can_add_lang,
        "can_continue_text": text,
    }


async def get_success_data(dialog_manager: DialogManager, **kwargs):
    d = dialog_manager.dialog_data
    m_type = d.get("movie_type") or d.get("exist_type")
    existing = d.get("existing_langs", [])
    can_add_more = len(existing) < len(LANGUAGES)

    cur_lang = d.get("language", "uz")
    cur_lang_code = get_lang_code(cur_lang)
    lang_info = next(
        (f"{l['flag']} {l['label']}" for l in LANGUAGES if l["id"] == cur_lang_code),
        cur_lang,
    )

    if m_type == "feature_film":
        save_info = str(_("Film"))
    else:
        ep = d.get("series")
        sn = d.get("season")
        if m_type == "series":
            save_info = str(_("Sezon {sn}, Qism {ep}").format(sn=sn, ep=ep))
        else:
            save_info = str(_("Qism {ep}").format(ep=ep))

    saved_files = d.get("files", {})
    fmt_keys = [k for k in saved_files.keys() if k != "original"]
    fmt_text = ", ".join(fmt_keys) if fmt_keys else "Original"

    success_msg = str(
        _(
            "✅ <b>Muvaffaqiyatli saqlandi!</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "🎬 <b>{info}</b>\n"
            "🌍 <b>Til:</b> {lang}\n"
            "📊 <b>Formatlar:</b> {formats}\n"
            "━━━━━━━━━━━━━━━\n\n"
            "{action_prompt}"
        ).format(
            info=save_info,
            lang=lang_info,
            formats=fmt_text,
            action_prompt=_("Nima qilamiz?"),
        )
    )

    return {
        "is_not_film": m_type != "feature_film",
        "can_add_more_langs": can_add_more,
        "success_msg": success_msg,
    }


async def get_summary(dialog_manager: DialogManager, **kwargs):
    import logging

    logger = logging.getLogger(__name__)
    data = dialog_manager.dialog_data
    logger.info(f"DEBUG: get_summary data keys: {list(data.keys())}")
    if "file_id" in data:
        logger.info(f"DEBUG: file_id={data['file_id']}")
    if "thumbnail_file_id" in data:
        logger.info(f"DEBUG: thumbnail_file_id={data['thumbnail_file_id']}")
    movie_type = data.get("movie_type")
    category = data.get("category")

    types_map = {
        "cat_film": {
            "feature_film": _("TYPE_MOVIE"),
            "series": _("TYPE_SERIES"),
            "mini_series": _("TYPE_MINI_SERIES"),
        },
        "cat_multi": {
            "feature_film": _("TYPE_CARTOON_MOVIE"),
            "series": _("TYPE_CARTOON_SERIES"),
            "mini_series": _("TYPE_CARTOON_MINI_SERIES"),
        },
        "cat_anime": {
            "feature_film": _("TYPE_ANIME_MOVIE"),
            "series": _("TYPE_ANIME_SERIES"),
            "mini_series": _("TYPE_ANIME_MINI_SERIES"),
        },
    }
    cats = {
        "cat_film": _("CAT_MOVIES"),
        "cat_multi": _("CAT_CARTOONS"),
        "cat_anime": _("CAT_ANIME"),
    }

    from src.app.bot.common.utils import format_multi_caption, format_multi_name

    cur_lang = data.get("language", "uz")
    cur_lang_code = get_lang_code(cur_lang)
    lang_display = next(
        (f"{l['flag']} {l['label']}" for l in LANGUAGES if l["id"] == cur_lang_code),
        cur_lang,
    )

    raw_name = data.get("name")
    if isinstance(raw_name, dict):
        from src.app.bot.common.utils import deep_flatten_name

        flat_name = deep_flatten_name(raw_name)
        if isinstance(flat_name, dict):
            display_name = flat_name.get(cur_lang_code) or next(
                (v for v in flat_name.values() if isinstance(v, str) and v.strip()),
                format_multi_name(raw_name),
            )
        else:
            display_name = str(flat_name)
    else:
        display_name = format_multi_name(raw_name)

    raw_caption = data.get("caption") or ""
    if isinstance(raw_caption, dict):
        from src.app.bot.common.utils import deep_flatten_name

        flat_cap = deep_flatten_name(raw_caption)
        if isinstance(flat_cap, dict):
            display_caption = flat_cap.get(cur_lang_code) or next(
                (v for v in flat_cap.values() if isinstance(v, str) and v.strip()), ""
            )
        else:
            display_caption = str(flat_cap)
    else:
        display_caption = str(raw_caption) if raw_caption else ""

    summary = (
        f"{_('SUM_TITLE')}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{_('SUM_CATEGORY')} {cats.get(category, category)}\n"
        f"{_('SUM_TYPE')} {types_map.get(category, {}).get(movie_type, movie_type)}\n"
        f"{_('SUM_CODE')} <code>{data.get('code')}</code>\n"
        f"{_('SUM_LANG')} {lang_display}\n"
        f"{_('SUM_NAME')} {display_name}\n"
        f"{_('SUM_GENRES')} {get_genre_display_text(data.get('genres', []))}\n"
    )
    if movie_type == "series":
        summary += f"{_('SUM_SEASON')} {data.get('season')}\n"
        summary += f"{_('SUM_SERIES')} {data.get('series')}\n"
    elif movie_type == "mini_series":
        summary += f"{_('SUM_SERIES')} {data.get('series')}\n"

    summary += f"\n{_('SUM_CAPTION')}\n{display_caption if display_caption else str(_('Yo\'q'))}"
    summary += "\n━━━━━━━━━━━━━━━\n"

    file_id = data.get("file_id")
    thumbnail_id = data.get("thumbnail_file_id")
    preview_mode = data.get("preview_mode", "video")

    media = None
    if preview_mode == "thumbnail" and thumbnail_id:
        media = MediaAttachment(type=ContentType.PHOTO, file_id=MediaId(thumbnail_id))
    elif file_id:
        media = MediaAttachment(type=ContentType.VIDEO, file_id=MediaId(file_id))

    toggle_text = (
        str(_("🖼 Muqovani ko'rish"))
        if preview_mode == "video"
        else str(_("📹 Videoni ko'rish"))
    )

    return {
        "summary": summary,
        "media": media,
        "toggle_text": toggle_text,
        "is_series": movie_type == "series",
        "is_mini": movie_type == "mini_series",
        "is_not_film": movie_type in ["series", "mini_series"],
    }


# ─────────────────────────────────────────────
#  DIALOG
# ─────────────────────────────────────────────

add_movie_dialog = Dialog(
    Window(
        Format(_("🏷 <b>Kategoriyani tanlang:</b>")),
        Row(
            Button(Format("{cat_film}"), id="cat_film", on_click=on_category_selected),
            Button(
                Format("{cat_multi}"), id="cat_multi", on_click=on_category_selected
            ),
            Button(
                Format("{cat_anime}"), id="cat_anime", on_click=on_category_selected
            ),
        ),
        Cancel(Format(_("CAT_ADMIN_MENU"))),
        state=AddMovieWizardSG.choose_category,
        getter=get_category_selection_data,
    ),
    Window(
        Format(_("TYPE_SELECT_PROMPT")),
        Column(
            Button(
                Format("{type_film}"),
                id="feature_film",
                on_click=on_movie_type_selected,
            ),
            Button(
                Format("{type_series}"), id="series", on_click=on_movie_type_selected
            ),
            Button(
                Format("{type_mini}"), id="mini_series", on_click=on_movie_type_selected
            ),
        ),
        SwitchTo(
            Format(_("BTN_BACK")),
            id="back_to_category",
            state=AddMovieWizardSG.choose_category,
        ),
        state=AddMovieWizardSG.choose_type,
        getter=get_type_selection_data,
    ),
    Window(
        Format(_("🔢 <b>Kod (ID) kiriting:</b>\n(Faqat raqamlar)")),
        MessageInput(on_code_input, content_types=ContentType.TEXT),
        SwitchTo(
            Format(_("🔙 Ortga")), id="back_to_type", state=AddMovieWizardSG.choose_type
        ),
        state=AddMovieWizardSG.input_code,
    ),
    Window(
        Format(_("🔍 <b>Kod band!</b>\n\n{can_continue_text}")),
        Column(
            Button(
                Format(_("➕ Yangi til qo'shish")),
                id="q_add_lang",
                on_click=on_add_language,
                when="can_add_lang",
            ),
            Button(
                Format(_("✅ Yangi qism qo'shish")),
                id="q_next",
                when="can_continue",
                on_click=on_quick_next,
            ),
        ),
        SwitchTo(
            Format(_("🔙 Ortga")), id="back_to_code", state=AddMovieWizardSG.input_code
        ),
        state=AddMovieWizardSG.quick_add,
        getter=get_quick_add_data,
    ),
    Window(
        Format(_("🎬 <b>Film nomini kiriting:</b>")),
        MessageInput(on_name_input, content_types=ContentType.TEXT),
        Row(
            SwitchTo(
                Format(_("🔙 Ortga")),
                id="back_to_code_manual",
                state=AddMovieWizardSG.input_code,
            ),
            Button(
                Format(_("❌ Bekor")),
                id="cancel_to_type_name",
                on_click=on_cancel_to_type,
            ),
        ),
        state=AddMovieWizardSG.input_name,
        getter=get_type_specific_prompts,
    ),
    Window(
        Format(_("📅 <b>Sezon raqamini kiriting:</b>")),
        MessageInput(on_season_input, content_types=ContentType.TEXT),
        Row(
            SwitchTo(
                Format(_("🔙 Ortga")),
                id="back_to_name_s",
                state=AddMovieWizardSG.input_name,
            ),
            Button(
                Format(_("❌ Bekor")), id="cancel_to_type_s", on_click=on_cancel_to_type
            ),
        ),
        state=AddMovieWizardSG.input_season_number,
        getter=get_type_specific_prompts,
    ),
    Window(
        Format(_("🔢 <b>Qism raqamini kiriting:</b>")),
        MessageInput(on_series_num_input, content_types=ContentType.TEXT),
        Row(
            SwitchTo(
                Format(_("🔙 Ortga")),
                id="back_to_season_s",
                state=AddMovieWizardSG.input_season_number,
            ),
            Button(
                Format(_("❌ Bekor")),
                id="cancel_to_type_ep",
                on_click=on_cancel_to_type,
            ),
        ),
        state=AddMovieWizardSG.input_series_number,
        getter=get_type_specific_prompts,
    ),
    Window(
        Format(_("📹 <b>Video yoki faylni yuboring:</b>")),
        MessageInput(
            on_file_input, content_types=[ContentType.VIDEO, ContentType.DOCUMENT]
        ),
        Row(
            SwitchTo(
                Format(_("🔙 Ortga")),
                id="back_to_prev_f",
                state=AddMovieWizardSG.input_name,
            ),
            Button(
                Format(_("❌ Bekor")), id="cancel_to_type_f", on_click=on_cancel_to_type
            ),
        ),
        state=AddMovieWizardSG.input_file,
        getter=get_type_specific_prompts,
    ),
    Window(
        Format(
            _(
                "💿 <b>Video sifatini tanlang:</b>\n(Bu sifat asosida transkodlash amalga oshiriladi)"
            )
        ),
        Group(
            Select(
                Format("{item[1]}"),
                id="q_select",
                item_id_getter=lambda x: x[0],
                items="qualities",
                on_click=on_quality_selected,
            ),
            width=2,
        ),
        Button(
            Format(_("⏭ Avtomatik (Aniqlash)")),
            id="skip_quality",
            on_click=on_skip_quality,
        ),
        Row(
            SwitchTo(
                Format(_("🔙 Ortga")),
                id="back_to_file_q",
                state=AddMovieWizardSG.input_file,
            ),
        ),
        state=AddMovieWizardSG.select_input_quality,
        getter=get_quality_data,
    ),
    Window(
        Format("{caption_prompt}"),
        MessageInput(on_caption_input, content_types=ContentType.TEXT),
        Button(
            Format(_("⏭ O'tkazib yuborish")),
            id="skip_caption",
            on_click=on_skip_caption,
        ),
        Row(
            SwitchTo(
                Format(_("🔙 Ortga")),
                id="back_to_file_after_skip_format",
                state=AddMovieWizardSG.input_file,
            ),
            Button(
                Format(_("❌ Bekor")), id="cancel_to_type_c", on_click=on_cancel_to_type
            ),
        ),
        state=AddMovieWizardSG.input_caption,
        getter=get_type_specific_prompts,
    ),
    Window(
        Format(_("🖼 <b>Muqova rasmini yuboring:</b>\n<i>(Ixtiyoriy)</i>")),
        MessageInput(
            on_thumbnail_input, content_types=[ContentType.PHOTO, ContentType.DOCUMENT]
        ),
        Button(Format(_("Skip ⏭")), id="skip_thumbnail", on_click=on_skip_thumbnail),
        Row(
            SwitchTo(
                Format(_("🔙 Ortga")),
                id="back_to_caption_th",
                state=AddMovieWizardSG.input_caption,
            ),
            Button(
                Format(_("❌ Bekor")),
                id="cancel_to_type_th",
                on_click=on_cancel_to_type,
            ),
        ),
        state=AddMovieWizardSG.input_thumbnail,
    ),
    Window(
        Format("{language_mode_prompt}"),
        Group(
            Select(
                Format("{item[flag]} {item[label]}"),
                id="lang_select",
                item_id_getter=lambda x: x["id"],
                items="languages",
                on_click=on_language_selected,
            ),
            width=2,
        ),
        MessageInput(on_language_input, content_types=ContentType.TEXT),
        Row(
            SwitchTo(
                Format(_("🔙 Ortga")),
                id="back_to_caption",
                state=AddMovieWizardSG.input_caption,
            ),
            Button(
                Format(_("❌ Bekor")),
                id="cancel_to_type_lang",
                on_click=on_cancel_to_type,
            ),
        ),
        state=AddMovieWizardSG.input_language,
        getter=[get_type_specific_prompts, get_language_data],
    ),
    Window(
        Format(
            _(
                "🎭 <b>Janrlarni tanlang:</b>\n<i>(Bir nechta tanlash mumkin)</i>\n\n<b>Tanlangan:</b> {selected_text}"
            )
        ),
        Group(
            Select(
                Format("{item[1]}"),
                id="g_select",
                item_id_getter=lambda x: x[0],
                items="genres",
                on_click=on_genre_toggle,
            ),
            id="g_group",
            width=2,
        ),
        Button(
            Format(_("✅ Tasdiqlash")), id="confirm_genres", on_click=on_genre_toggle
        ),
        Row(
            SwitchTo(
                Format(_("🔙 Xulosa")),
                id="back_to_confirm",
                state=AddMovieWizardSG.confirm,
                when=lambda d, w, m: m.dialog_data.get("editing_field") == "e_genres",
            ),
            SwitchTo(
                Format(_("🔙 Ortga")),
                id="back_to_language",
                state=AddMovieWizardSG.input_language,
                when=lambda d, w, m: m.dialog_data.get("editing_field") != "e_genres",
            ),
        ),
        state=AddMovieWizardSG.select_genres,
        getter=get_genre_data,
    ),
    Window(
        DynamicMedia("media"),
        Format("{summary}"),
        Row(
            Button(Format(_("💾 Saqlash")), id="save", on_click=on_confirm),
            Button(
                Format(_("📱 Postni ko'rish")),
                id="btn_post_preview",
                on_click=on_post_preview_click,
            ),
        ),
        Row(
            Button(
                Format("{toggle_text}"), id="toggle_preview", on_click=on_toggle_preview
            ),
            Button(Format(_("✏️ Tahrir")), id="edit", on_click=on_edit_click),
        ),
        Button(
            Format(_("❌ Bekor")), id="cancel_to_type_final", on_click=on_cancel_to_type
        ),
        state=AddMovieWizardSG.confirm,
        getter=get_summary,
    ),
    Window(
        DynamicMedia("media"),
        Format("{summary}"),
        Format(_("\n🛠 <b>Nimani o'zgartirish?</b>")),
        Row(
            Button(
                Format("{toggle_text}"),
                id="toggle_preview_e",
                on_click=on_toggle_preview,
            ),
            SwitchTo(
                Format(_("✅ Saqlashga")),
                id="back_to_hub_save",
                state=AddMovieWizardSG.confirm,
            ),
            SwitchTo(
                Format(_("🔙 Ortga")),
                id="back_to_confirm_e",
                state=AddMovieWizardSG.confirm,
            ),
        ),
        Column(
            Button(
                Format(_("🔢 Kod (ID)")), id="e_code", on_click=on_edit_field_selected
            ),
            Button(Format(_("📛 Nomi")), id="e_name", on_click=on_edit_field_selected),
            Button(
                Format(_("🎭 Janrlar")), id="e_genres", on_click=on_edit_field_selected
            ),
            Button(
                Format(_("📄 Tavsif")), id="e_caption", on_click=on_edit_field_selected
            ),
            Button(
                Format(_("🖼 Muqova")), id="e_thumbnail", on_click=on_edit_field_selected
            ),
            Button(
                Format(_("📹 Video")), id="e_video", on_click=on_edit_field_selected
            ),
            Button(Format(_("🌍 Til")), id="e_language", on_click=on_edit_language),
            Button(
                Format(_("📅 Sezon")),
                id="e_season",
                on_click=on_edit_field_selected,
                when="is_series",
            ),
            Button(
                Format(_("🎞 Qism")),
                id="e_series",
                on_click=on_edit_field_selected,
                when="is_not_film",
            ),
        ),
        state=AddMovieWizardSG.edit_menu,
        getter=get_summary,
    ),
    Window(
        Format("{prompt}"),
        MessageInput(on_field_edit_input),
        SwitchTo(
            Format(_("🔙 Ortga")),
            id="back_to_edit_menu",
            state=AddMovieWizardSG.edit_menu,
        ),
        state=AddMovieWizardSG.edit_field,
        getter=get_edit_data,
    ),
    Window(
        Format("{success_msg}"),
        Column(
            Button(
                Format(_("➕ Yana til qo'shish")),
                id="add_another_lang",
                on_click=on_add_language,
                when="can_add_more_langs",
            ),
            Button(
                Format(_("➕ Keyingi qism")),
                id="continue_loop",
                on_click=on_add_more,
                when="is_not_film",
            ),
            Button(Format(_("🔙 Boshiga")), id="back_type", on_click=on_back_to_type),
            Button(
                Format(_("🏠 Bosh menyu")),
                id="finish_admin",
                on_click=on_finish_to_admin,
            ),
        ),
        state=AddMovieWizardSG.success,
        getter=get_success_data,
    ),
    Window(
        DynamicMedia("media"),
        Format("{caption}"),
        Row(
            Button(Format("{publish_label}"), id="publish", on_click=on_post_publish),
            Button(Format("{refresh_label}"), id="refresh", on_click=on_refresh_post),
        ),
        Row(
            Button(
                Format("{prev_label}"),
                id="prev_img",
                on_click=on_prev_poster,
                when="has_prev",
            ),
            Button(Format("{counter}"), id="counter_img"),
            Button(
                Format("{next_label}"),
                id="next_img",
                on_click=on_next_poster,
                when="has_next",
            ),
        ),
        Row(
            SwitchTo(
                Format("{img_edit_label}"),
                id="edit_img",
                state=AddMovieWizardSG.edit_post_image,
            ),
            SwitchTo(
                Format("{cap_edit_label}"),
                id="edit_cap",
                state=AddMovieWizardSG.edit_post_caption,
            ),
        ),
        Row(
            SwitchTo(
                Format("{btn_edit_search_name}"),
                id="edit_search_name",
                state=AddMovieWizardSG.edit_post_search_name,
            ),
        ),
        Row(
            SwitchTo(
                Format("{lang_select_label}"),
                id="go_to_lang",
                state=AddMovieWizardSG.post_lang_menu,
            ),
            SwitchTo(
                Format("{back_label}"),
                id="back_to_confirm_post",
                state=AddMovieWizardSG.confirm,
            ),
        ),
        state=AddMovieWizardSG.post_preview,
        getter=get_post_preview_data,
    ),
    Window(
        Format("{lang_select_label}"),
        Row(
            Select(
                Format("{item[1]}"),
                id="post_lang",
                items=[("uz", "🇺🇿 UZ"), ("ru", "🇷🇺 RU"), ("en", "🇺🇸 EN")],
                item_id_getter=lambda x: x[0],
                on_click=on_post_lang_change,
            ),
        ),
        SwitchTo(
            Format("{back_label}"),
            id="back_to_preview",
            state=AddMovieWizardSG.post_preview,
        ),
        state=AddMovieWizardSG.post_lang_menu,
        getter=get_post_preview_data,
    ),
    Window(
        Format("{img_prompt}"),
        MessageInput(on_edit_post_image_input),
        SwitchTo(
            Format("{back_label}"), id="cancel_img", state=AddMovieWizardSG.post_preview
        ),
        state=AddMovieWizardSG.edit_post_image,
        getter=get_post_preview_data,
    ),
    Window(
        Format("{cap_prompt}"),
        MessageInput(on_edit_post_caption_input),
        SwitchTo(
            Format("{back_label}"), id="cancel_cap", state=AddMovieWizardSG.post_preview
        ),
        state=AddMovieWizardSG.edit_post_caption,
        getter=get_post_preview_data,
    ),
    Window(
        Format("{search_name_prompt}"),
        MessageInput(on_edit_post_search_name_input),
        SwitchTo(
            Format("{back_label}"), id="cancel_search", state=AddMovieWizardSG.post_preview
        ),
        state=AddMovieWizardSG.edit_post_search_name,
        getter=get_post_preview_data,
    ),
)
