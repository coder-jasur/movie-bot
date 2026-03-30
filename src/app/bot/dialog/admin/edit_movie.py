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
from aiogram_dialog.widgets.text import Const, Format, Multi
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.common.genres import (
    GENRES,
    deserialize_genres,
    get_genre_display_text,
    serialize_genres,
)
from src.app.bot.common.i18n import lazy_gettext as _
from src.app.bot.common.languages import LANGUAGES
from src.app.bot.common.utils import get_lang_code, send_admin_preview_media_group
from src.app.bot.states.admin.dialogs import EditMovieSG
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

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────


def get_actions(session: AsyncSession, category: str, m_type: str):
    if category == "film":
        if m_type == "feature_film":
            return FeatureFilmsActions(session)
        if m_type == "series":
            return SeriesActions(session)
        if m_type == "mini_series":
            return MiniSeriesActions(session)
    elif category == "multi_film":
        if m_type == "feature_film":
            return MultiFilmFeatureActions(session)
        if m_type == "series":
            return MultiFilmSeriesActions(session)
        if m_type == "mini_series":
            return MultiFilmMiniSeriesActions(session)
    elif category == "anime":
        if m_type == "feature_film":
            return AnimeFeatureActions(session)
        if m_type == "series":
            return AnimeSeriesActions(session)
        if m_type == "mini_series":
            return AnimeMiniSeriesActions(session)
    return None


# ─────────────────────────────────────────────
#  HANDLERS
# ─────────────────────────────────────────────


async def on_edit_genres_click(c: CallbackQuery, widget: Any, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    code = manager.dialog_data["code"]
    m_type = manager.dialog_data["type"]
    category = manager.dialog_data["category"]
    actions = get_actions(session, category, m_type)

    genres_json = None
    if m_type == "feature_film":
        ff = await actions.get_feature_film(code)
        genres_json = ff.genres if ff else None
    else:
        genres_json = await actions.get_genres_by_code(code)

    manager.dialog_data["genres"] = deserialize_genres(genres_json)
    manager.dialog_data["return_state"] = manager.current_context().state
    await manager.switch_to(EditMovieSG.edit_genres)


async def on_genre_toggle(
    c: CallbackQuery, widget: Any, manager: DialogManager, item_id: str = None
):
    if widget.widget_id == "save_genres":
        session: AsyncSession = manager.middleware_data["session"]
        code = manager.dialog_data["code"]
        m_type = manager.dialog_data["type"]
        genres_list = manager.dialog_data.get("genres", [])
        genres_ser = serialize_genres(genres_list)
        category = manager.dialog_data["category"]
        actions = get_actions(session, category, m_type)
        await actions.update_genres(code, genres_ser)
        if "obj" in manager.dialog_data:
            manager.dialog_data["obj"]["genres"] = genres_ser
        await c.answer(str(_("✅ Janrlar yangilandi!")))
        await on_back_click(c, widget, manager)
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


async def _trigger_edit_preview(manager: DialogManager):
    """Effectively no-op, buttons show within dialog now."""
    manager.show_mode = ShowMode.SEND


async def transition_to_editing(m: Message, dialog_manager: DialogManager, code: int):
    if not dialog_manager.dialog_data.get("exists"):
        await m.answer(str(_("❌ {code} kodli kontent topilmadi!")).format(code=code))
        return

    m_type = dialog_manager.dialog_data.get("type")
    obj = dialog_manager.dialog_data.get("obj", {})
    session: AsyncSession = dialog_manager.middleware_data["session"]
    category = dialog_manager.dialog_data.get("category")
    actions = get_actions(session, category, m_type)

    if m_type == "feature_film":
        langs = [l for l in (obj.get("language") or "").split(",") if l]
    else:
        if m_type == "series":
            eps = await actions.get_series(code)
        else:
            eps = await actions.get_mini_series(code)
        seen = set()
        langs = []
        for ep in eps or []:
            for l in (ep.language or "").split(","):
                if l and l not in seen:
                    seen.add(l)
                    langs.append(l)

    dialog_manager.dialog_data["all_langs"] = langs
    dialog_manager.dialog_data["return_to_lang"] = "search"

    if len(langs) >= 1:
        await dialog_manager.switch_to(EditMovieSG.select_language)
    else:
        await _trigger_edit_preview(dialog_manager)
        await dialog_manager.switch_to(EditMovieSG.select_action)


async def on_code_search(m: Message, widget: Any, manager: DialogManager):
    if not m.text.isdigit():
        await m.answer(str(_("❌ Raqam kiriting!")))
        return

    code = int(m.text)
    manager.dialog_data.clear()
    session: AsyncSession = manager.middleware_data["session"]

    search_map = [
        (FeatureFilmsActions, "feature_film", "film"),
        (MiniSeriesActions, "mini_series", "film"),
        (SeriesActions, "series", "film"),
        (MultiFilmFeatureActions, "feature_film", "multi_film"),
        (MultiFilmMiniSeriesActions, "mini_series", "multi_film"),
        (MultiFilmSeriesActions, "series", "multi_film"),
        (AnimeFeatureActions, "feature_film", "anime"),
        (AnimeMiniSeriesActions, "mini_series", "anime"),
        (AnimeSeriesActions, "series", "anime"),
    ]

    matches = []
    for ActionClass, m_type, cat in search_map:
        actions = ActionClass(session)
        if m_type == "feature_film":
            result = await actions.get_feature_film(code)
        elif m_type == "series":
            result = await actions.get_series(code)
        else:
            result = await actions.get_mini_series(code)

        if not result:
            continue

        matches.append((result, m_type, cat))

    if not matches:
        manager.dialog_data["exists"] = False
        await transition_to_editing(m, manager, code)
        return

    # Agar bir nechta turdagi kontent topilsa (masalan, film va serial)
    # Hozircha birinchisini olamiz
    result, m_type, cat = matches[0]

    if m_type == "feature_film":
        obj_data = {
            "name": result.name,
            "caption": result.captions,
            "genres": result.genres,
            "language": result.language,
            "files": result.files,
            "thumbnails": result.thumbnails,
            "captions": result.captions,
        }
    else:
        obj_data = {
            "name": result[0].name,
            "genres": result[0].genres,
            "language": result[0].language,
            "thumbnails": result[0].thumbnails,
        }

    manager.dialog_data.update(
        {
            "type": m_type,
            "category": cat,
            "code": code,
            "obj": obj_data,
            "exists": True,
        }
    )
    await transition_to_editing(m, manager, code)


async def on_toggle_edit_preview(c: CallbackQuery, widget: Any, manager: DialogManager):
    current = manager.dialog_data.get("preview_mode", "video")
    manager.dialog_data["preview_mode"] = "thumbnail" if current == "video" else "video"
    await c.answer()


async def on_back_click(c: CallbackQuery, widget: Button, manager: DialogManager):
    return_state = manager.dialog_data.get("return_state", EditMovieSG.select_action)
    await _trigger_edit_preview(manager)
    await manager.switch_to(return_state)


async def on_set_return_action(c: CallbackQuery, widget: Any, manager: DialogManager):
    manager.dialog_data["return_state"] = EditMovieSG.select_action


async def on_set_return_details(c: CallbackQuery, widget: Any, manager: DialogManager):
    manager.dialog_data["return_to"] = "details"
    manager.dialog_data["return_state"] = EditMovieSG.edit_episode_details


async def on_open_langs(c: CallbackQuery, widget: Any, manager: DialogManager):
    if manager.current_context().state == EditMovieSG.edit_episode_details:
        manager.dialog_data["return_to_lang"] = "details"
    else:
        manager.dialog_data["return_to_lang"] = "action"
    await manager.switch_to(EditMovieSG.select_language)


async def on_edit_name(m: Message, widget: Any, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    code = manager.dialog_data["code"]
    m_type = manager.dialog_data["type"]
    new_name = m.text
    ep_id = manager.dialog_data.get("selected_episode_id")
    category = manager.dialog_data["category"]
    actions = get_actions(session, category, m_type)

    try:
        lang = manager.dialog_data.get("selected_lang_track")
        if ep_id:
            if not lang:
                if m_type == "series":
                    s, n = map(int, ep_id.split(":"))
                    eps = await actions.get_series(code)
                    match = next(
                        (e for e in eps if e.season == s and e.series == n), None
                    )
                    lang = (
                        (match.language or "").split(",")[0]
                        if match and match.language
                        else "uz"
                    )
                elif m_type == "mini_series":
                    n = int(ep_id)
                    eps = await actions.get_mini_series(code)
                    match = next((e for e in eps if e.series == n), None)
                    lang = (
                        (match.language or "").split(",")[0]
                        if match and match.language
                        else "uz"
                    )

            if m_type == "series":
                s, n = map(int, ep_id.split(":"))
                await actions.update_language_track(code, s, n, lang, name=new_name)
            elif m_type == "mini_series":
                n = int(ep_id)
                await actions.update_language_track(code, n, lang, name=new_name)
            await m.answer(str(_("✅ Qism nomi yangilandi!")))
            await manager.switch_to(EditMovieSG.edit_episode_details)
        else:
            if m_type == "feature_film":
                if not lang:
                    ff = await actions.get_feature_film(code)
                    lang = (
                        (ff.language or "").split(",")[0]
                        if ff and ff.language
                        else "uz"
                    )
                await actions.update_language_track(code, lang, name=new_name)
                if "obj" in manager.dialog_data:
                    manager.dialog_data["obj"]["name"] = new_name
                await m.answer(str(_("✅ Nomi yangilandi!")))
                await manager.switch_to(EditMovieSG.select_action)
    except Exception as e:
        await m.answer(str(_("❌ Xato: {error}")).format(error=html.escape(str(e))))


async def on_edit_caption(m: Message, widget: Any, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    code = manager.dialog_data["code"]
    m_type = manager.dialog_data["type"]
    new_caption = m.html_text if m.caption else m.text
    ep_id = manager.dialog_data.get("selected_episode_id")
    category = manager.dialog_data["category"]
    actions = get_actions(session, category, m_type)

    try:
        lang = manager.dialog_data.get("selected_lang_track")
        if ep_id:
            if m_type == "series":
                s, n = map(int, ep_id.split(":"))
                if not lang:
                    eps = await actions.get_series(code)
                    match = next(
                        (e for e in eps if e.season == s and e.series == n), None
                    )
                    lang = ((match.language or "").split(",") or ["uz"])[0]
                await actions.update_language_track(
                    code, s, n, lang, caption=new_caption
                )
            elif m_type == "mini_series":
                n = int(ep_id)
                if not lang:
                    eps = await actions.get_mini_series(code)
                    match = next((e for e in eps if e.series == n), None)
                    lang = ((match.language or "").split(",") or ["uz"])[0]
                await actions.update_language_track(code, n, lang, caption=new_caption)
            await m.answer(str(_("✅ Qism tavsifi yangilandi!")))
            await manager.switch_to(EditMovieSG.edit_episode_details)
        else:
            if m_type == "feature_film":
                if not lang:
                    ff = await actions.get_feature_film(code)
                    langs = (ff.language or "").split(",") if ff else []
                    lang = langs[0] if langs and langs[0] else "uz"
                await actions.update_language_track(code, lang, caption=new_caption)
                if "obj" in manager.dialog_data:
                    if not isinstance(manager.dialog_data["obj"].get("captions"), dict):
                        manager.dialog_data["obj"]["captions"] = {}
                    manager.dialog_data["obj"]["captions"][lang] = new_caption
                    manager.dialog_data["obj"]["caption"] = manager.dialog_data["obj"][
                        "captions"
                    ]
                await m.answer(str(_("✅ Tavsif yangilandi!")))
                await manager.switch_to(EditMovieSG.select_action)
    except Exception as e:
        await m.answer(str(_("❌ Xato: {error}")).format(error=html.escape(str(e))))


async def on_edit_language(m: Message, widget: Any, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    code = manager.dialog_data["code"]
    m_type = manager.dialog_data["type"]
    new_lang = m.text
    category = manager.dialog_data["category"]
    actions = get_actions(session, category, m_type)

    try:
        lang_id = get_lang_code(new_lang)
        if m_type == "feature_film":
            await actions.update_feature_film(code, language=lang_id)
        elif m_type == "series":
            await actions.update_series(code, language=lang_id)
        elif m_type == "mini_series":
            await actions.update_mini_series(code, language=lang_id)
        manager.dialog_data["obj"]["language"] = lang_id
        await m.answer(str(_("✅ Til yangilandi!")))
        await manager.switch_to(EditMovieSG.select_action)
    except Exception as e:
        await m.answer(str(_("❌ Xato: {error}")).format(error=html.escape(str(e))))


async def on_language_selected(
    c: CallbackQuery, widget: Any, manager: DialogManager, item_id: str
):
    manager.dialog_data["language"] = item_id
    await c.answer(str(_("Tanlandi: {lang}")).format(lang=item_id))
    ret = manager.dialog_data.get("return_to")
    if ret == "details":
        await _trigger_edit_preview(manager)
        await manager.switch_to(EditMovieSG.edit_episode_details)
    else:
        await _trigger_edit_preview(manager)
        await manager.switch_to(EditMovieSG.select_action)


async def on_track_selected(
    c: CallbackQuery, widget: Any, manager: DialogManager, item_id: str
):
    manager.dialog_data["selected_lang_track"] = item_id
    await c.answer(str(_("Track tanlandi: {lang}")).format(lang=item_id))
    ret = manager.dialog_data.get("return_to_lang")
    if ret == "details":
        await _trigger_edit_preview(manager)
        await manager.switch_to(EditMovieSG.edit_episode_details)
    else:
        await _trigger_edit_preview(manager)
        await manager.switch_to(EditMovieSG.select_action)


async def on_back_from_langs(c: CallbackQuery, widget: Any, manager: DialogManager):
    ret = manager.dialog_data.get("return_to_lang")
    if ret == "search":
        await manager.switch_to(EditMovieSG.input_code)
    elif ret == "details":
        await manager.switch_to(EditMovieSG.edit_episode_details)
    else:
        await manager.switch_to(EditMovieSG.select_action)


async def on_delete_track(c: CallbackQuery, widget: Any, manager: DialogManager):
    lang = manager.dialog_data.get("selected_lang_track")
    if not lang:
        await c.answer(str(_("⚠️ Avval tilni tanlang!")), show_alert=True)
        return

    session: AsyncSession = manager.middleware_data["session"]
    code = manager.dialog_data["code"]
    m_type = manager.dialog_data["type"]
    category = manager.dialog_data["category"]
    actions = get_actions(session, category, m_type)

    try:
        ep_id = manager.dialog_data.get("selected_episode_id")
        if ep_id:
            if m_type == "series":
                s, n = map(int, ep_id.split(":"))
                await actions.delete_language_track(code, s, n, lang)
            elif m_type == "mini_series":
                n = int(ep_id)
                await actions.delete_language_track(code, n, lang)
        else:
            await actions.delete_language_track(code, lang)

        await c.answer(str(_("✅ Til tracki o'chirildi!")))
        manager.dialog_data.pop("selected_lang_track", None)
        await manager.switch_to(EditMovieSG.select_language)
    except Exception as e:
        await c.answer(
            str(_("❌ Xato: {error}")).format(error=html.escape(str(e))),
            show_alert=True,
        )


async def on_add_lang_edit(c: CallbackQuery, widget: Any, manager: DialogManager):
    from src.app.bot.states.admin.dialogs import AddMovieWizardSG

    code = manager.dialog_data.get("code")
    await manager.start(AddMovieWizardSG.input_code, data={"code": code})


async def on_edit_code(m: Message, widget: Any, manager: DialogManager):
    if not m.text.isdigit():
        await m.answer(str(_("❌ Raqam kiriting!")))
        return

    new_code = int(m.text)
    old_code = manager.dialog_data["code"]
    m_type = manager.dialog_data["type"]
    session: AsyncSession = manager.middleware_data["session"]
    ep_id = manager.dialog_data.get("selected_episode_id")
    category = manager.dialog_data["category"]
    actions = get_actions(session, category, m_type)

    try:
        if ep_id:
            if m_type == "series":
                s, n = map(int, ep_id.split(":"))
                await actions.move_to_feature_film(old_code, s, n, new_code)
            elif m_type == "mini_series":
                n = int(ep_id)
                await actions.move_to_feature_film(old_code, n, new_code)
            await m.answer(
                str(_("✅ Qism film sifatida ajratildi! Yangi kod: {code}")).format(
                    code=new_code
                )
            )
            await manager.switch_to(EditMovieSG.input_code)
        else:
            await actions.update_movie_code(old_code, new_code)
            await m.answer(str(_("✅ Kod muvaffaqiyatli o'zgartirildi!")))
            manager.dialog_data["code"] = new_code
            await manager.switch_to(EditMovieSG.select_action)
    except Exception as e:
        await m.answer(str(_("❌ Xato: {error}")).format(error=html.escape(str(e))))


async def on_edit_file(m: Message, widget: Any, manager: DialogManager):
    """
    Video faylni qabul qilib, transcoder orqali formatlaydi va
    aynan shu tildagi barcha eski formatlarni yangi formatlar bilan almashtiradi.
    """
    if m.video:
        raw_file_id = m.video.file_id
    elif m.document:
        raw_file_id = m.document.file_id
    else:
        await m.answer(str(_("❌ Video yoki fayl yuboring.")))
        return

    session: AsyncSession = manager.middleware_data["session"]
    code = manager.dialog_data["code"]
    m_type = manager.dialog_data["type"]
    ep_id = manager.dialog_data.get("selected_episode_id")
    category = manager.dialog_data["category"]
    actions = get_actions(session, category, m_type)

    # ── Tilni aniqlash ───────────────────────────────────────
    lang = manager.dialog_data.get("selected_lang_track")
    if not lang:
        try:
            if m_type == "feature_film":
                ff = await actions.get_feature_film(code)
                langs = [l for l in (ff.language or "").split(",") if l] if ff else []
                lang = langs[0] if langs else "uz"
            elif m_type == "series" and ep_id:
                s, n = map(int, ep_id.split(":"))
                eps = await actions.get_series(code)
                match = next((e for e in eps if e.season == s and e.series == n), None)
                lang = (
                    ((match.language or "").split(",") or ["uz"])[0] if match else "uz"
                )
            elif m_type == "mini_series" and ep_id:
                n = int(ep_id)
                eps = await actions.get_mini_series(code)
                match = next((e for e in eps if e.series == n), None)
                lang = (
                    ((match.language or "").split(",") or ["uz"])[0] if match else "uz"
                )
        except Exception:
            pass
    lang = lang or "uz"

    # ── Transcoding ──────────────────────────────────────────
    # ── Celery Task ishlatamiz ────────────────────────────────
    from src.app.services.tasks import process_video_task

    status_msg = await m.answer(str(_("⏳ Video tayyorlanmoqda (Local Worker)...")))
    admin_locale = manager.middleware_data.get("i18n").current_locale

    # Get existing thumbnail if available
    obj = manager.dialog_data.get("obj", {})
    thumbnails = obj.get("thumbnails") or {}
    thumbnail_id = thumbnails.get(lang) or next(iter(thumbnails.values()), None)

    task_data = {
        "admin_id": m.from_user.id,
        "status_msg_id": status_msg.message_id,
        "admin_locale": admin_locale,
        "file_id": raw_file_id,
        "thumbnail_file_id": thumbnail_id,
        "category": category,
        "movie_type": m_type,
        "code": code,
        "language": lang,
        "is_editing": True,
        "ep_id": ep_id,
        "is_adding_track": False,  # Bu yerda tahrirlash ketmoqda
    }

    process_video_task.delay(task_data)

    await m.answer(
        str(
            _(
                "🚀 Faylni yangilash vazifasi navbatga qo'shildi. Jarayon tugagach sizga xabar yuboriladi."
            )
        )
    )
    await manager.switch_to(EditMovieSG.select_action)
    return


async def on_edit_thumbnail(m: Message, widget: Any, manager: DialogManager):
    """Photo yoki document qabul qilib thumbnail_file_id ni yangilaydi."""
    if m.photo:
        new_thumbnail_id = m.photo[-1].file_id
    elif (
        m.document
        and m.document.mime_type
        and m.document.mime_type.startswith("image/")
    ):
        new_thumbnail_id = m.document.file_id
    else:
        await m.answer(str(_("❌ Rasm yuboring (foto yoki rasm fayl).")))
        return

    session: AsyncSession = manager.middleware_data["session"]
    code = manager.dialog_data["code"]
    m_type = manager.dialog_data["type"]
    category = manager.dialog_data["category"]
    actions = get_actions(session, category, m_type)

    # Determine language
    lang = manager.dialog_data.get("selected_lang_track") or "uz"

    try:
        if m_type == "feature_film":
            await actions.update_language_track(
                code, lang, thumbnail_file_id=new_thumbnail_id
            )
        elif m_type == "series":
            ep_id = manager.dialog_data.get("selected_episode_id")
            if ep_id:
                s, n = map(int, ep_id.split(":"))
                await actions.update_language_track(
                    code, s, n, lang, thumbnail_file_id=new_thumbnail_id
                )
            else:
                # Global thumb update - for now updates all or defaults to 'uz'
                await actions.update_series(code, thumbnail_file_id=new_thumbnail_id)
        elif m_type == "mini_series":
            ep_id = manager.dialog_data.get("selected_episode_id")
            if ep_id:
                n = int(ep_id)
                await actions.update_language_track(
                    code, n, lang, thumbnail_file_id=new_thumbnail_id
                )
            else:
                await actions.update_mini_series(
                    code, thumbnail_file_id=new_thumbnail_id
                )
        await m.answer(str(_("✅ Muqova muvaffaqiyatli yangilandi!")))
        if "obj" in manager.dialog_data:
            if not isinstance(manager.dialog_data["obj"].get("thumbnails"), dict):
                manager.dialog_data["obj"]["thumbnails"] = {}
            manager.dialog_data["obj"]["thumbnails"][lang] = new_thumbnail_id
        await _trigger_edit_preview(manager)
        await manager.switch_to(EditMovieSG.select_action)
    except Exception as e:
        await m.answer(str(_("❌ Xato: {error}")).format(error=html.escape(str(e))))


async def on_skip_edit_thumbnail(c: CallbackQuery, widget: Any, manager: DialogManager):
    """Thumbnail o'chirish (None qilish)."""
    session: AsyncSession = manager.middleware_data["session"]
    code = manager.dialog_data["code"]
    m_type = manager.dialog_data["type"]
    category = manager.dialog_data["category"]
    actions = get_actions(session, category, m_type)

    # Determine language
    lang = manager.dialog_data.get("selected_lang_track") or "uz"

    try:
        if m_type == "feature_film":
            await actions.update_language_track(code, lang, thumbnail_file_id=None)
        elif m_type == "series":
            ep_id = manager.dialog_data.get("selected_episode_id")
            if ep_id:
                s, n = map(int, ep_id.split(":"))
                await actions.update_language_track(
                    code, s, n, lang, thumbnail_file_id=None
                )
            else:
                await actions.update_series(code, thumbnail_file_id=None)
        elif m_type == "mini_series":
            ep_id = manager.dialog_data.get("selected_episode_id")
            if ep_id:
                n = int(ep_id)
                await actions.update_language_track(
                    code, n, lang, thumbnail_file_id=None
                )
            else:
                await actions.update_mini_series(code, thumbnail_file_id=None)
        await c.answer(str(_("✅ Muqova o'chirildi!")))
        if "obj" in manager.dialog_data and "thumbnails" in manager.dialog_data["obj"]:
            if isinstance(manager.dialog_data["obj"]["thumbnails"], dict):
                manager.dialog_data["obj"]["thumbnails"].pop(lang, None)
        await manager.switch_to(EditMovieSG.select_action)
    except Exception as e:
        await c.answer(
            str(_("❌ Xato: {error}")).format(error=html.escape(str(e))),
            show_alert=True,
        )


async def on_season_selected(
    c: CallbackQuery, widget: Any, manager: DialogManager, item_id: str
):
    manager.dialog_data["selected_season"] = int(item_id)
    await manager.switch_to(EditMovieSG.select_episode)


async def on_episode_selected(
    c: CallbackQuery, widget: Any, manager: DialogManager, item_id: str
):
    manager.dialog_data["selected_episode_id"] = item_id
    session: AsyncSession = manager.middleware_data["session"]
    code = manager.dialog_data["code"]
    m_type = manager.dialog_data["type"]
    category = manager.dialog_data["category"]
    actions = get_actions(session, category, m_type)

    langs = []
    try:
        if m_type == "series":
            s, n = map(int, item_id.split(":"))
            eps = await actions.get_series(code)
            match = next((e for e in eps if e.season == s and e.series == n), None)
            if match:
                langs = (match.language or "").split(",")
        elif m_type == "mini_series":
            n = int(item_id)
            eps = await actions.get_mini_series(code)
            match = next((e for e in eps if e.series == n), None)
            if match:
                langs = (match.language or "").split(",")
    except Exception:
        pass

    langs = [l for l in langs if l]
    if len(langs) > 1:
        track = manager.dialog_data.get("selected_lang_track")
        if track and track in langs:
            await _trigger_edit_preview(manager)
            await manager.switch_to(EditMovieSG.edit_episode_details)
        else:
            manager.dialog_data["return_to_lang"] = "details"
            await manager.switch_to(EditMovieSG.select_language)
    else:
        if langs:
            manager.dialog_data["selected_lang_track"] = langs[0]
        await _trigger_edit_preview(manager)
        await manager.switch_to(EditMovieSG.edit_episode_details)


async def on_edit_episode_num(m: Message, widget: Any, manager: DialogManager):
    if not m.text.isdigit():
        await m.answer(str(_("❌ Raqam kiriting!")))
        return

    new_num = int(m.text)
    session: AsyncSession = manager.middleware_data["session"]
    code = manager.dialog_data["code"]
    m_type = manager.dialog_data["type"]
    ep_id = manager.dialog_data["selected_episode_id"]
    category = manager.dialog_data["category"]

    try:
        if m_type == "series":
            season, old_num = map(int, ep_id.split(":"))
            actions = get_actions(session, category, "series")
            eps = await actions.get_series(code)
            if any(e.season == season and e.series == new_num for e in eps):
                await m.answer(str(_("❌ {n}-qism allaqachon band!")).format(n=new_num))
                return
            await actions.update_episode_details(code, season, old_num, series=new_num)
            manager.dialog_data["selected_episode_id"] = f"{season}:{new_num}"
        elif m_type == "mini_series":
            old_num = int(ep_id)
            actions = get_actions(session, category, "mini_series")
            eps = await actions.get_mini_series(code)
            if any(e.series == new_num for e in eps):
                await m.answer(str(_("❌ {n}-qism allaqachon band!")).format(n=new_num))
                return
            await actions.update_episode_details(code, old_num, series=new_num)
            manager.dialog_data["selected_episode_id"] = str(new_num)

        await m.answer(str(_("✅ Qism raqami yangilandi!")))
        await manager.switch_to(EditMovieSG.edit_episode_details)
    except Exception as e:
        await m.answer(str(_("❌ Xato: {error}")).format(error=html.escape(str(e))))


async def on_edit_season_num(m: Message, widget: Any, manager: DialogManager):
    """
    FIX: Oldin `manager.current_context().state == EditMovieSG.edit_season_num`
    tekshiruvi har doim True bo'lardi (chunki handler faqat shu state dan chaqiriladi).
    Endi `editing_mode` flag orqali individual/global ajratiladi.
    """
    if not m.text.isdigit():
        await m.answer(str(_("❌ Raqam kiriting!")))
        return

    new_season = int(m.text)
    session: AsyncSession = manager.middleware_data["session"]
    code = manager.dialog_data["code"]
    category = manager.dialog_data["category"]
    actions = get_actions(session, category, "series")

    # FIX: editing_mode flag orqali ajratamiz
    editing_mode = manager.dialog_data.get("season_editing_mode", "individual")

    try:
        if editing_mode == "individual":
            # Individual episode season change
            ep_id = manager.dialog_data["selected_episode_id"]
            season, num = map(int, ep_id.split(":"))
            eps = await actions.get_series(code)
            if any(e.season == new_season and e.series == num for e in eps):
                await m.answer(
                    str(_("❌ Sezon {s}, qism {n} allaqachon mavjud!")).format(
                        s=new_season, n=num
                    )
                )
                return
            await actions.update_episode_details(code, season, num, season=new_season)
            manager.dialog_data["selected_episode_id"] = f"{new_season}:{num}"
            await m.answer(str(_("✅ Bu qismning sezon raqami yangilandi!")))
            await manager.switch_to(EditMovieSG.edit_episode_details)
        else:
            # Global season rename
            old_season = manager.dialog_data["selected_season"]
            eps = await actions.get_series(code)
            if any(e.season == new_season for e in eps):
                await m.answer(
                    str(_("❌ {n}-sezon allaqachon mavjud!")).format(n=new_season)
                )
                return
            await actions.update_global_season_selective(code, old_season, new_season)
            manager.dialog_data["selected_season"] = new_season
            await m.answer(
                str(_("✅ {old}-sezon {new}-sezonga o'zgartirildi!")).format(
                    old=old_season, new=new_season
                )
            )
            await manager.switch_to(EditMovieSG.select_episode)
    except Exception as e:
        await m.answer(str(_("❌ Xato: {error}")).format(error=html.escape(str(e))))


async def on_edit_season_individual(
    c: CallbackQuery, widget: Any, manager: DialogManager
):
    """Set mode = individual before switching to season edit."""
    manager.dialog_data["season_editing_mode"] = "individual"
    await manager.switch_to(EditMovieSG.edit_season_num)


async def on_edit_season_global(c: CallbackQuery, widget: Any, manager: DialogManager):
    """Set mode = global before switching to season edit."""
    manager.dialog_data["season_editing_mode"] = "global"
    await manager.switch_to(EditMovieSG.edit_global_season)


async def on_delete_confirm(c: CallbackQuery, widget: Any, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    code = manager.dialog_data["code"]
    m_type = manager.dialog_data["type"]
    category = manager.dialog_data["category"]
    actions = get_actions(session, category, m_type)

    try:
        if m_type == "feature_film":
            await actions.delete_feature_film(code)
        elif m_type == "mini_series":
            await actions.delete_mini_series(code)
        elif m_type == "series":
            await actions.delete_series(code)
        await c.message.answer(str(_("✅ Muvaffaqiyatli o'chirildi.")))
        await manager.switch_to(EditMovieSG.input_code)
    except Exception as e:
        await c.message.answer(
            str(_("❌ Xato: {error}")).format(error=html.escape(str(e)))
        )


async def on_delete_episode_confirm(
    c: CallbackQuery, widget: Any, manager: DialogManager
):
    session: AsyncSession = manager.middleware_data["session"]
    code = manager.dialog_data["code"]
    m_type = manager.dialog_data["type"]
    category = manager.dialog_data["category"]
    actions = get_actions(session, category, m_type)
    selected_ep_id = manager.dialog_data.get("selected_episode_id")

    try:
        if m_type == "series":
            s, n = map(int, selected_ep_id.split(":"))
            await actions.delete_series_for_season(code, n, s)
        elif m_type == "mini_series":
            n = int(selected_ep_id)
            await actions.delete_mini_series_for_series(code, n)
        await c.message.answer(str(_("✅ Qism muvaffaqiyatli o'chirildi.")))
        await manager.switch_to(EditMovieSG.select_episode)
    except Exception as e:
        await c.message.answer(
            str(_("❌ Xato: {error}")).format(error=html.escape(str(e)))
        )


async def on_delete_season_confirm(
    c: CallbackQuery, widget: Any, manager: DialogManager
):
    session: AsyncSession = manager.middleware_data["session"]
    category = manager.dialog_data["category"]
    code = manager.dialog_data["code"]
    actions = get_actions(session, category, "series")
    season = manager.dialog_data.get("selected_season")

    try:
        await actions.delete_season(code, season)
        await c.message.answer(
            str(_("✅ {season}-sezon o'chirildi.")).format(season=season)
        )
        await manager.switch_to(EditMovieSG.select_season)
    except Exception as e:
        await c.message.answer(str(_("❌ Xato: {error}")).format(error=str(e)))


# ─────────────────────────────────────────────
#  GETTERS
# ─────────────────────────────────────────────


async def get_movie_info(dialog_manager: DialogManager, **kwargs):
    session: AsyncSession = dialog_manager.middleware_data["session"]
    data = dialog_manager.dialog_data.get("obj", {})
    code = dialog_manager.dialog_data.get("code")
    m_type = dialog_manager.dialog_data.get("type")
    category = dialog_manager.dialog_data.get("category")
    actions = get_actions(session, category, m_type)

    if m_type == "feature_film" and actions:
        fresh_data = await actions.get_feature_film(code)
        if fresh_data:
            data = {
                "name": fresh_data.name,
                "caption": fresh_data.captions,
                "files": fresh_data.files,
                "genres": fresh_data.genres,
                "language": fresh_data.language,
                "thumbnails": fresh_data.thumbnails,
                "captions": fresh_data.captions,
            }
            dialog_manager.dialog_data["obj"] = data

    labels_map = {
        "film": {
            "feature_film": _("🎬 Film"),
            "series": _("🎞 Serial"),
            "mini_series": _("🎥 Mini-serial"),
        },
        "multi_film": {
            "feature_film": _("🧸 Mult film"),
            "series": _("🎞 Mult serial"),
            "mini_series": _("🎥 Mult mini-serial"),
        },
        "anime": {
            "feature_film": _("🏮 Anime film"),
            "series": _("🎞 Anime serial"),
            "mini_series": _("🎥 Anime mini-serial"),
        },
    }
    type_labels = labels_map.get(category, {})

    seasons = []
    episodes = []
    selected_ep = {}
    total_eps = 0
    total_seasons = 0
    
    # 🚀 MEDIA RESOLUTION LOGIC
    # User requirement: No video until language is selected.
    file_id = None
    thumbnail_id = None
    target_quality = None

    from src.app.bot.common.utils import get_user_language, resolve_movie_media

    sel_lang = dialog_manager.dialog_data.get("selected_lang_track")
    preview_lang = sel_lang or await get_user_language(
        dialog_manager.event.from_user, session
    )

    class MovieProxy:
        def __init__(self, d):
            self.files = d.get("files")
            self.captions = d.get("captions")
            self.language = d.get("language")
            self.name = d.get("name")

    if sel_lang:
        try:
            # We treat admins as VIPs (is_vip=True) to allow 720p/1080p previews.
            res_file, _n, _c, _d, _q, _e, _f, res_thumb = resolve_movie_media(
                MovieProxy(data), sel_lang, is_vip=True
            )
            file_id = res_file
            thumbnail_id = res_thumb
            target_quality = _q
        except Exception as e:
            logger.debug(f"Initial resolve_movie_media failed: {e}")

    # Sifat: files dict kalitlaridan format nomlarini olamiz
    LANG_CODES = {
        "uz", "ru", "en", "kz", "uk", "de", "fr", "es", "it", "tr", "ar", "fa", "hi", "zh", "ja",
    }

    def extract_quality(files) -> str:
        if not files or not isinstance(files, dict):
            return "Original"
        first_val = next(iter(files.values()), None)
        if isinstance(first_val, dict):
            all_fmt = set()
            for v in files.values():
                if isinstance(v, dict):
                    for k in v.keys():
                        k_str = str(k).lower()
                        if k_str not in LANG_CODES:
                            all_fmt.add("Original" if k_str == "original" else str(k))
            return ", ".join(sorted(all_fmt)) if all_fmt else "Original"
        else:
            fmt_keys = []
            for k in files.keys():
                k_str = str(k).lower()
                if k_str not in LANG_CODES:
                    fmt_keys.append("Original" if k_str == "original" else str(k))
            return ", ".join(fmt_keys) if fmt_keys else "Original"

    files_dict = data.get("files") or {}
    target_quality = extract_quality(files_dict)

    if m_type == "series" and actions:
        try:
            eps = await actions.get_series(code)
            if sel_lang:
                eps = [e for e in eps if sel_lang in (e.language or "").split(",")]
            total_eps = len(eps)
            unique_seasons = sorted(list(set(e.season for e in eps)))
            total_seasons = len(unique_seasons)
            seasons = [(str(s), f"📅 {s}-{_('sezon')}") for s in unique_seasons]
            sel_s = dialog_manager.dialog_data.get("selected_season")
            if sel_s:
                s_eps = [e for e in eps if e.season == sel_s]
                episodes = [(f"{e.season}:{e.series}", str(e.series)) for e in s_eps]
            selected_ep_id = dialog_manager.dialog_data.get("selected_episode_id")
            if selected_ep_id and sel_lang:
                s, n = map(int, selected_ep_id.split(":"))
                match = next((e for e in eps if e.season == s and e.series == n), None)
                if match:
                    from src.app.bot.common.utils import (
                        format_multi_caption,
                        format_multi_name,
                    )

                    try:
                        res_file, _n, _c, _d, _tq, _e, _f, thumbnail_id = (
                            resolve_movie_media(match, sel_lang, is_vip=True)
                        )
                        file_id = res_file
                        target_quality = _tq
                    except Exception:
                        file_id = match.video_file_id
                    
                    selected_ep = {
                        "season": match.season,
                        "episode": match.series,
                        "file_id": file_id,
                        "name": format_multi_name(match.name, sel_lang),
                        "caption": format_multi_caption(match.captions, sel_lang),
                        "code": match.code,
                        "files": match.files,
                        "languages": [
                            l for l in (match.language or "").split(",") if l
                        ],
                        "quality": target_quality or "Original",
                    }
        except Exception:
            pass

    elif m_type == "mini_series" and actions:
        try:
            eps = await actions.get_mini_series(code)
            if sel_lang:
                eps = [e for e in eps if sel_lang in (e.language or "").split(",")]
            total_eps = len(eps)
            episodes = [(str(e.series), str(e.series)) for e in eps]
            selected_ep_id = dialog_manager.dialog_data.get("selected_episode_id")
            if selected_ep_id and sel_lang:
                n = int(selected_ep_id)
                match = next((e for e in eps if e.series == n), None)
                if match:
                    from src.app.bot.common.utils import (
                        format_multi_caption,
                        format_multi_name,
                    )

                    try:
                        res_file, _n, _c, _d, _tq, _e, _f, thumbnail_id = (
                            resolve_movie_media(match, sel_lang, is_vip=True)
                        )
                        file_id = res_file
                        target_quality = _tq
                    except Exception:
                        file_id = match.video_file_id

                    selected_ep = {
                        "episode": match.series,
                        "file_id": file_id,
                        "name": format_multi_name(match.name, sel_lang),
                        "caption": format_multi_caption(match.captions, sel_lang),
                        "code": match.code,
                        "files": match.files,
                        "languages": [
                            l for l in (match.language or "").split(",") if l
                        ],
                        "quality": target_quality or "Original",
                    }
        except Exception:
            pass

    preview_mode = dialog_manager.dialog_data.get("preview_mode", "video")
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

    existing_langs = (
        (data.get("language") or "").split(",")
        if m_type == "feature_film"
        else selected_ep.get("languages", [])
    )
    lang_labels = []
    for l_id in existing_langs:
        if not l_id:
            continue
        label = next((l["label"] for l in LANGUAGES if l["id"] == l_id), l_id.upper())
        lang_labels.append(str(label))
    lang_info = ", ".join(lang_labels) if lang_labels else str(_("ko'rsatilmagan"))

    sel_lang_label = str(_("tanlanmagan"))
    if sel_lang:
        sel_lang_label = next(
            (str(l["label"]) for l in LANGUAGES if l["id"] == sel_lang),
            sel_lang.upper(),
        )

    from src.app.bot.common.utils import format_multi_caption, format_multi_name

    return {
        "code": code,
        "name": format_multi_name(data.get("name"), sel_lang),
        "caption": format_multi_caption(data.get("caption"), sel_lang),
        "type": m_type,
        "type_label": type_labels.get(m_type, str(_("Noma'lum"))),
        "is_series": m_type == "series",
        "is_mini_series": m_type == "mini_series",
        "is_film": m_type == "feature_film",
        "total_eps": total_eps,
        "total_seasons": total_seasons,
        "seasons": seasons,
        "episodes": episodes,
        "selected_ep": selected_ep,
        "selected_season": dialog_manager.dialog_data.get("selected_season"),
        "media": media,
        "toggle_text": toggle_text,
        "genres_text": get_genre_display_text(deserialize_genres(data.get("genres"))),
        "format": data.get("format"),
        "language": lang_info,
        "existing_langs": existing_langs,
        "selected_lang_label": sel_lang_label,
        "quality": target_quality or "Original",
    }


async def get_language_tracks_data(dialog_manager: DialogManager, **kwargs):
    d = dialog_manager.dialog_data
    m_type = d.get("type")
    session: AsyncSession = dialog_manager.middleware_data["session"]
    code = d.get("code")
    category = d.get("category")

    cached = d.get("all_langs")
    if cached is not None:
        langs = cached
    elif m_type == "feature_film":
        langs = [l for l in (d.get("obj", {}).get("language") or "").split(",") if l]
    else:
        actions = get_actions(session, category, m_type)
        if m_type == "series":
            eps = await actions.get_series(code) if code else []
        else:
            eps = await actions.get_mini_series(code) if code else []
        seen = set()
        langs = []
        for ep in eps or []:
            for l in (ep.language or "").split(","):
                if l and l not in seen:
                    seen.add(l)
                    langs.append(l)

    track_items = []
    for l_id in langs:
        if not l_id:
            continue
        label = next(
            (str(l["label"]) for l in LANGUAGES if l["id"] == l_id), l_id.upper()
        )
        track_items.append({"id": l_id, "label": label})

    from src.app.bot.common.utils import format_multi_name

    sel_lang = d.get("selected_lang_track")
    return {
        "tracks": track_items,
        "name": format_multi_name(d.get("obj", {}).get("name"), sel_lang),
        "selected_lang_track": sel_lang,
    }


async def get_edit_prompts(dialog_manager: DialogManager, **kwargs):
    category = dialog_manager.dialog_data.get("category")
    m_type = dialog_manager.dialog_data.get("type")

    cat_prefix = ""
    if category == "anime":
        cat_prefix = _("anime-")
    elif category == "multi_film":
        cat_prefix = _("mult-")

    target = _("film") if m_type == "feature_film" else _("serial")
    if dialog_manager.dialog_data.get("selected_episode_id"):
        target = _("qism")

    return {
        "name_prompt": str(
            _("📝 <b>Yangi nom kiriting ({prefix}{target}):</b>")
        ).format(prefix=cat_prefix, target=target),
        "caption_prompt": str(
            _("📄 <b>Yangi tavsif kiriting ({prefix}{target}):</b>")
        ).format(prefix=cat_prefix, target=target),
        "code_prompt": str(
            _("🔢 <b>Yangi kod (ID) kiriting ({prefix}{target}):</b>")
        ).format(prefix=cat_prefix, target=target),
        "file_prompt": str(
            _("📹 <b>Yangi video fayl yuboring ({prefix}{target}):</b>")
        ).format(prefix=cat_prefix, target=target),
        "season_prompt": str(_("📅 <b>Yangi sezon raqamini kiriting:</b>")),
        "series_prompt": str(_("🔢 <b>Yangi qism raqamini kiriting:</b>")),
        "language_prompt": str(
            _("🌍 <b>Yangi til kiriting ({prefix}{target}):</b>")
        ).format(prefix=cat_prefix, target=target),
    }


async def get_genre_data(dialog_manager: DialogManager, **kwargs):
    selected_genres = dialog_manager.dialog_data.get("genres", [])
    genre_list = []
    for g in GENRES:
        name = g["name"]
        checkmark = "✅ " if name in selected_genres else ""
        genre_list.append((name, f"{checkmark}{str(g['label'])}"))

    from src.app.bot.common.utils import format_multi_name

    sel_lang = dialog_manager.dialog_data.get("selected_lang_track")

    return {
        "name": format_multi_name(
            dialog_manager.dialog_data.get("obj", {}).get("name"), sel_lang
        ),
        "genres": genre_list,
        "selected_text": get_genre_display_text(selected_genres),
    }


async def get_language_data(dialog_manager: DialogManager, **kwargs):
    return {"languages": LANGUAGES}


async def get_labels(dialog_manager: DialogManager, **kwargs):
    return {"cancel": str(_("⬅️ Bekor")), "back": str(_("⬅️ Ortga"))}


async def get_season_data(dialog_manager: DialogManager, **kwargs):
    return {
        "media": None,
        "selected_season": dialog_manager.dialog_data.get("selected_season"),
    }


# ─────────────────────────────────────────────
#  DIALOG
# ─────────────────────────────────────────────

edit_movie_dialog = Dialog(
    Window(
        Format(_("🔢 <b>Kontent kodini (ID) kiriting:</b>")),
        MessageInput(on_code_search, content_types=ContentType.TEXT),
        Cancel(Format("{cancel}"), id="cancel"),
        state=EditMovieSG.input_code,
        getter=get_labels,
    ),
    Window(
        DynamicMedia("media"),
        Multi(
            Format(
                _(
                    "📋 <b>MA'LUMOT:</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "<b>🏷 Tur:</b> {type_label}\n"
                    "<b>🔢 Kod ID:</b> <code>{code}</code>\n"
                    "<b>🎬 Nomi:</b> <i>{name}</i>\n"
                    "<b>🎭 Janrlar:</b> {genres_text}\n"
                    "<b>📍 Tanlangan:</b> {selected_lang_label}\n"
                )
            ),
            Format(
                _("<b>📊 Sifat:</b> {quality}\n<b>🌍 Tracklar:</b> {language}\n"),
                when="is_film",
            ),
            Format(
                _(
                    "<b>📅 Sezonlar:</b> {total_seasons}\n<b>🎞 Qismlar:</b> {total_eps}\n"
                ),
                when="is_series",
            ),
            Format(_("<b>🎞 Qismlar:</b> {total_eps}\n"), when="is_mini_series"),
            Format(_("<b>📄 Tavsif:</b>\n{caption}\n"), when="is_film"),
            Format(_("━━━━━━━━━━━━━━━━━━━━━\n<b>AMALLAR:</b>")),
        ),
        Row(
            Button(
                Format("{toggle_text}"),
                id="toggle_preview_edit",
                on_click=on_toggle_edit_preview,
            ),
        ),
        Column(
            SwitchTo(
                Format(_("✏️ Nomini o'zgartirish")),
                id="en",
                state=EditMovieSG.edit_name,
                when="is_film",
                on_click=on_set_return_action,
            ),
            SwitchTo(
                Format(_("📄 Tavsifni o'zgartirish")),
                id="ec",
                state=EditMovieSG.edit_caption,
                when="is_film",
                on_click=on_set_return_action,
            ),
            SwitchTo(
                Format(_("🔢 Kod ID o'zgartirish")),
                id="ecd",
                state=EditMovieSG.edit_code,
                on_click=on_set_return_action,
            ),
            Button(
                Format(_("🌍 Tillar")),
                id="el_btn",
                on_click=on_open_langs,
                when="is_film",
            ),
            SwitchTo(
                Format(_("📹 Video o'zgartirish")),
                id="ef",
                state=EditMovieSG.edit_file,
                when="is_film",
                on_click=on_set_return_action,
            ),
            SwitchTo(
                Format(_("📷 Muqova o'zgartirish")),
                id="eth",
                state=EditMovieSG.edit_thumbnail,
                when="is_film",
                on_click=on_set_return_action,
            ),
            Button(
                Format(_("🎭 Janrlarni o'zgartirish")),
                id="eg_btn",
                on_click=on_edit_genres_click,
            ),
            SwitchTo(
                Format(_("📅 Sezonlar boshqaruvi")),
                id="es",
                state=EditMovieSG.select_season,
                when="is_series",
            ),
            SwitchTo(
                Format(_("🎞 Qismlar boshqaruvi")),
                id="ee",
                state=EditMovieSG.select_episode,
                when="is_mini_series",
            ),
            SwitchTo(
                Format(_("🗑 To'liq o'chirish")),
                id="db",
                state=EditMovieSG.confirm_delete,
            ),
        ),
        SwitchTo(Format(_("⬅️ Qidiruvga")), id="bm", state=EditMovieSG.input_code),
        state=EditMovieSG.select_action,
        getter=get_movie_info,
    ),
    Window(
        Format(_("🌍 <b>Tillar boshqaruvi:</b>\n«{name}»")),
        Group(
            Select(
                Format("{item[label]}"),
                id="track_select",
                item_id_getter=lambda x: x["id"],
                items="tracks",
                on_click=on_track_selected,
            ),
            width=2,
        ),
        Button(
            Format(_("➕ Yangi til qo'shish")),
            id="add_lang_edit",
            on_click=on_add_lang_edit,
        ),
        Button(
            Format(_("🗑 Tanlangan tilni o'chirish")),
            id="del_track",
            on_click=on_delete_track,
            when="selected_lang_track",
        ),
        Button(
            Format(_("⬅️ Ortga")), id="back_from_tracks", on_click=on_back_from_langs
        ),
        state=EditMovieSG.select_language,
        getter=[get_movie_info, get_language_tracks_data],
    ),
    Window(
        Format("{name_prompt}"),
        MessageInput(on_edit_name, content_types=ContentType.TEXT),
        Button(Format(_("« Ortga")), id="b1", on_click=on_back_click),
        state=EditMovieSG.edit_name,
        getter=get_edit_prompts,
    ),
    Window(
        Format("{caption_prompt}"),
        MessageInput(on_edit_caption, content_types=ContentType.TEXT),
        Button(Format(_("« Ortga")), id="b2", on_click=on_back_click),
        state=EditMovieSG.edit_caption,
        getter=get_edit_prompts,
    ),
    Window(
        Format("{code_prompt}"),
        MessageInput(on_edit_code, content_types=ContentType.TEXT),
        Button(Format(_("« Ortga")), id="b3", on_click=on_back_click),
        state=EditMovieSG.edit_code,
        getter=get_edit_prompts,
    ),
    Window(
        Format(_("📹 {file_prompt}")),
        MessageInput(
            on_edit_file, content_types=[ContentType.VIDEO, ContentType.DOCUMENT]
        ),
        Button(Format(_("⬅️ Ortga")), id="b4", on_click=on_back_click),
        state=EditMovieSG.edit_file,
        getter=get_edit_prompts,
    ),
    Window(
        Format(
            _(
                "📷 <b>Yangi muqova rasmini yuboring:</b>\n<i>(O'chirib tashlash uchun quyidagi tugmani bosing)</i>"
            )
        ),
        MessageInput(
            on_edit_thumbnail, content_types=[ContentType.PHOTO, ContentType.DOCUMENT]
        ),
        Button(
            Format(_("🗑 Muqovani o'chirish")),
            id="del_thumbnail",
            on_click=on_skip_edit_thumbnail,
        ),
        Button(Format(_("⬅️ Ortga")), id="b4_th", on_click=on_back_click),
        state=EditMovieSG.edit_thumbnail,
    ),
    Window(
        Format("{language_prompt}"),
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
        MessageInput(on_edit_language, content_types=ContentType.TEXT),
        Button(Format(_("« Ortga")), id="b4_l", on_click=on_back_click),
        state=EditMovieSG.edit_language,
        getter=[get_edit_prompts, get_language_data],
    ),
    Window(
        Format(_("📅 <b>Sezonni tanlang:</b>")),
        Group(
            Select(
                Format("{item[1]}"),
                id="s_s",
                item_id_getter=lambda x: x[0],
                items="seasons",
                on_click=on_season_selected,
            ),
            id="sg",
            width=2,
        ),
        SwitchTo(Format(_("⬅️ Ortga")), id="b5", state=EditMovieSG.select_action),
        state=EditMovieSG.select_season,
        getter=get_movie_info,
    ),
    Window(
        Format(_("🎞 <b>Qismlar ({selected_season}-sezon):</b>"), when="is_series"),
        Format(_("🎞 <b>Qismni tanlang:</b>"), when=lambda d, *a: not d["is_series"]),
        Group(
            Select(
                Format("{item[1]}"),
                id="se",
                item_id_getter=lambda x: x[0],
                items="episodes",
                on_click=on_episode_selected,
            ),
            id="eg",
            width=4,
        ),
        Column(
            Button(
                Format(_("🔢 Sezon raqamini o'zgartirish")),
                id="rs",
                on_click=on_edit_season_global,
                when="is_series",
            ),
            SwitchTo(
                Format(_("🗑 Butun sezonni o'chirish")),
                id="ds",
                state=EditMovieSG.confirm_delete_season,
                when="is_series",
            ),
        ),
        SwitchTo(
            Format(_("⬅️ Sezonlarga")),
            id="bs",
            state=EditMovieSG.select_season,
            when="is_series",
        ),
        SwitchTo(
            Format(_("⬅️ Ortga")),
            id="bm2",
            state=EditMovieSG.select_action,
            when=lambda d, *a: not d["is_series"],
        ),
        state=EditMovieSG.select_episode,
        getter=get_movie_info,
    ),
    Window(
        DynamicMedia("media"),
        Multi(
            Format(
                _(
                    "🛠 <b>QISM (Sezon {selected_ep[season]}, Qism {selected_ep[episode]}):</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "<b>🔢 Kod ID:</b> <code>{selected_ep[code]}</code>\n"
                    "<b>🎬 Nomi:</b> {selected_ep[name]}\n"
                    "<b>📊 Sifat:</b> {selected_ep[quality]}\n"
                    "<b>🎭 Janrlar:</b> {genres_text}\n"
                    "<b>🌍 Tracklar:</b> {language}\n"
                    "<b>📍 Tanlangan:</b> {selected_lang_label}\n"
                    "<b>📄 Tavsif:</b>\n{selected_ep[caption]}"
                ),
                when="is_series",
            ),
            Format(
                _(
                    "🛠 <b>QISM (Raqam {selected_ep[episode]}):</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "<b>🔢 Kod ID:</b> <code>{selected_ep[code]}</code>\n"
                    "<b>🎬 Nomi:</b> {selected_ep[name]}\n"
                    "<b>📊 Sifat:</b> {selected_ep[quality]}\n"
                    "<b>🎭 Janrlar:</b> {genres_text}\n"
                    "<b>🌍 Tracklar:</b> {language}\n"
                    "<b>📍 Tanlangan:</b> {selected_lang_label}\n"
                    "<b>📄 Tavsif:</b>\n{selected_ep[caption]}"
                ),
                when="is_mini_series",
            ),
        ),
        Row(
            Button(
                Format("{toggle_text}"),
                id="toggle_preview_edit_ep",
                on_click=on_toggle_edit_preview,
            ),
        ),
        Column(
            Button(
                Format(_("🎭 Janrlarni o'zgartirish")),
                id="eg_btn_ep",
                on_click=on_edit_genres_click,
            ),
            Button(Format(_("🌍 Tillar")), id="el_btn_ep", on_click=on_open_langs),
            SwitchTo(
                Format(_("📹 Video faylni o'zgartirish")),
                id="ef1",
                state=EditMovieSG.edit_file,
                on_click=on_set_return_details,
            ),
            SwitchTo(
                Format(_("✏️ Nomini o'zgartirish")),
                id="en1",
                state=EditMovieSG.edit_name,
                on_click=on_set_return_details,
            ),
            SwitchTo(
                Format(_("📄 Tavsifni o'zgartirish")),
                id="ec1",
                state=EditMovieSG.edit_caption,
                on_click=on_set_return_details,
            ),
            SwitchTo(
                Format(_("🔢 Filmga ajratish (Yangi kod)")),
                id="ec2",
                state=EditMovieSG.edit_code,
                on_click=on_set_return_details,
            ),
            Button(
                Format(_("📅 Sezon raqamini o'zgartirish")),
                id="es1",
                on_click=on_edit_season_individual,
                when="is_series",
            ),
            SwitchTo(
                Format(_("🔢 Qism raqamini o'zgartirish")),
                id="en2",
                state=EditMovieSG.edit_episode_num,
                on_click=on_set_return_details,
            ),
            SwitchTo(
                Format(_("🗑 Qismni o'chirish")),
                id="ed",
                state=EditMovieSG.confirm_delete_episode,
            ),
        ),
        SwitchTo(Format(_("⬅️ Ortga")), id="be", state=EditMovieSG.select_episode),
        state=EditMovieSG.edit_episode_details,
        getter=get_movie_info,
    ),
    Window(
        Format("{season_prompt}"),
        MessageInput(on_edit_season_num, content_types=ContentType.TEXT),
        SwitchTo(Format(_("« Ortga")), id="b6", state=EditMovieSG.edit_episode_details),
        state=EditMovieSG.edit_season_num,
        getter=get_edit_prompts,
    ),
    Window(
        Format("{series_prompt}"),
        MessageInput(on_edit_episode_num, content_types=ContentType.TEXT),
        SwitchTo(Format(_("« Ortga")), id="b7", state=EditMovieSG.edit_episode_details),
        state=EditMovieSG.edit_episode_num,
        getter=get_edit_prompts,
    ),
    Window(
        Format(_("🔢 <b>{selected_season}-sezon uchun yangi raqam:</b>")),
        MessageInput(on_edit_season_num, content_types=ContentType.TEXT),
        SwitchTo(Format(_("⬅️ Ortga")), id="b8", state=EditMovieSG.select_episode),
        state=EditMovieSG.edit_global_season,
        getter=get_season_data,
    ),
    Window(
        Format(_("⚠️ <b>TO'LIQ O'CHIRISH?</b>\n\n«{name}» (ID: {code})?")),
        Button(Format(_("✅ Ha, o'chirish")), id="cd", on_click=on_delete_confirm),
        SwitchTo(Format(_("❌ Yo'q")), id="cn", state=EditMovieSG.select_action),
        state=EditMovieSG.confirm_delete,
        getter=get_movie_info,
    ),
    Window(
        Multi(
            Format(
                _(
                    "⚠️ <b>S{selected_ep[season]} Q{selected_ep[episode]} o'chirilsinmi?</b>"
                ),
                when="is_series",
            ),
            Format(
                _("⚠️ <b>{selected_ep[episode]}-qism o'chirilsinmi?</b>"),
                when="is_mini_series",
            ),
        ),
        Button(
            Format(_("✅ Ha, o'chirish")), id="ce", on_click=on_delete_episode_confirm
        ),
        SwitchTo(
            Format(_("❌ Yo'q")), id="cn2", state=EditMovieSG.edit_episode_details
        ),
        state=EditMovieSG.confirm_delete_episode,
        getter=get_movie_info,
    ),
    Window(
        Format(_("⚠️ <b>{selected_season}-sezon o'chirilsinmi?</b>")),
        Button(
            Format(_("✅ Ha, o'chirish")), id="cs", on_click=on_delete_season_confirm
        ),
        SwitchTo(Format(_("❌ Yo'q")), id="cn3", state=EditMovieSG.select_episode),
        state=EditMovieSG.confirm_delete_season,
        getter=get_season_data,
    ),
    Window(
        Format(
            _(
                "🎭 <b>«{name}» janrlari:</b>\n"
                "<i>(O'zgartirish uchun bosing)</i>\n\n"
                "<b>Tanlangan:</b> {selected_text}"
            )
        ),
        Group(
            Select(
                Format("{item[1]}"),
                id="g_select_edit",
                item_id_getter=lambda x: x[0],
                items="genres",
                on_click=on_genre_toggle,
            ),
            id="g_group_edit",
            width=2,
        ),
        Button(Format(_("✅ Saqlash")), id="save_genres", on_click=on_genre_toggle),
        Button(
            Format(_("⬅️ Ortga")), id="back_to_prev_from_genres", on_click=on_back_click
        ),
        state=EditMovieSG.edit_genres,
        getter=get_genre_data,
    ),
)
