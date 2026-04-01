import asyncio
import datetime
import json
import os
import tempfile

import aiofiles
from aiogram.types import CallbackQuery, ContentType, FSInputFile, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Cancel, Row
from aiogram_dialog.widgets.text import Format
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.common.i18n import lazy_gettext as _
from src.app.bot.states.admin.dialogs import BackupSG
from src.app.database.models import (
    AnimeFeature,
    AnimeMiniSeries,
    AnimeSeries,
    Favorite,
    FeatureFilm,
    MiniSeries,
    MultiFilmFeature,
    MultiFilmMiniSeries,
    MultiFilmSeries,
    Series,
    User,
)
from src.app.database.queries.backup import BackupQueries


def _tmp(prefix: str) -> str:
    """Create a named temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix=prefix)
    os.close(fd)
    return path


async def _write_json(path: str, data: list) -> None:
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=4))


async def _cleanup(*paths: str) -> None:
    for path in paths:
        try:
            await asyncio.to_thread(os.remove, path)
        except FileNotFoundError:
            pass


async def on_backup_users(c: CallbackQuery, button: Button, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    queries = BackupQueries(session)
    users = await queries.get_all_users()

    data = [
        {
            "tg_id": user.tg_id,
            "username": user.username,
            "status": user.status,
            "language_code": user.language_code,
            "is_premium": user.is_premium,
            "vip_status": user.vip_status,
            "vip_payment_history": user.vip_payment_history,
            "vip_expires_at": (
                user.vip_expires_at.isoformat() if user.vip_expires_at else None
            ),
            "referral_url": user.referral_url,
            "joined_count": user.joined_count,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
        for user in users
    ]

    path = _tmp("users_backup_")
    try:
        await _write_json(path, data)
        await c.message.answer_document(
            FSInputFile(path, filename=f"users_backup_{datetime.date.today()}.json"),
            caption=str(_("📁 Полный бэкап ВСЕХ пользователей")),
        )
    finally:
        await _cleanup(path)


async def on_backup_favorites(c: CallbackQuery, button: Button, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    queries = BackupQueries(session)
    favorites = await queries.get_all_favorites()

    data = [
        {
            "user_id": f.user_id,
            "movie_code": f.movie_code,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in favorites
    ]

    path = _tmp("favorites_backup_")
    try:
        await _write_json(path, data)
        await c.message.answer_document(
            FSInputFile(
                path, filename=f"favorites_backup_{datetime.date.today()}.json"
            ),
            caption=str(_("📂 Полный бэкап списка Избранного")),
        )
    finally:
        await _cleanup(path)


async def on_backup_movies(c: CallbackQuery, button: Button, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    queries = BackupQueries(session)
    today = datetime.date.today()

    def _film_row(f):
        return {
            "code": f.code,
            "name": f.name,
            "captions": f.captions,
            "genres": f.genres,
            "language": f.language,
            "files": f.files,
            "thumbnails": f.thumbnails,
            "views_count": f.views_count,
        }

    def _series_row(s):
        return {
            "code": s.code,
            "season": s.season,
            "series": s.series,
            "name": s.name,
            "captions": s.captions,
            "genres": s.genres,
            "language": s.language,
            "files": s.files,
            "thumbnails": s.thumbnails,
            "views_count": s.views_count,
        }

    def _mini_row(m):
        return {
            "code": m.code,
            "series": m.series,
            "name": m.name,
            "captions": m.captions,
            "genres": m.genres,
            "language": m.language,
            "files": m.files,
            "thumbnails": m.thumbnails,
            "views_count": m.views_count,
        }

    categories = [
        (
            await queries.get_all_feature_films(),
            _film_row,
            "feature_films",
            _("🎬 BBARCHA filmlarning to'liq zaxirasi"),
        ),
        (
            await queries.get_all_series(),
            _series_row,
            "series",
            _("📺 BARCHA seriallarning to'liq zaxirasi"),
        ),
        (
            await queries.get_all_mini_series(),
            _mini_row,
            "mini_series",
            _("📽 BARCHA epizodli filmlarning to'liq zaxirasi"),
        ),
        (
            await queries.get_all_multi_film_features(),
            [_film_row],
            "multi_film_features",
            _("🧸 BARCHA multfilmlarning to'liq zaxirasi"),
        ),
        (
            await queries.get_all_multi_film_series(),
            _series_row,
            "multi_film_series",
            _("📺 BARCHA mult-seriallarning to'liq zaxirasi"),
        ),
        (
            await queries.get_all_multi_film_mini_series(),
            _mini_row,
            "multi_film_mini_series",
            _("📽 BARCHA epizodli multfilmlarning to'liq zaxirasi"),
        ),
        (
            await queries.get_all_anime_features(),
            _film_row,
            "anime_features",
            _("🏮 BARCHA anime filmlarning to'liq zaxirasi"),
        ),
        (
            await queries.get_all_anime_series(),
            _series_row,
            "anime_series",
            _("📺 BARCHA anime seriallarning to'liq zaxirasi"),
        ),
        (
            await queries.get_all_anime_mini_series(),
            _mini_row,
            "anime_mini_series",
            _("📽 BARCHA epizodli animelarning to'liq zaxirasi"),
        ),
    ]

    paths = []
    try:
        for records, row_fn, name, caption in categories:
            path = _tmp(f"backup_{name}_")
            paths.append(path)
            await _write_json(path, [row_fn(r) for r in records])
            await c.message.answer_document(
                FSInputFile(path, filename=f"backup_{name}_{today}.json"),
                caption=str(caption),
            )
    finally:
        await _cleanup(*paths)


async def _backup_menu_getter(**kwargs):
    return {
        "menu_title": str(
            _("💾 <b>Меню бэкапа</b>\n\nВыберите тип данных для выгрузки:")
        ),
        "btn_users": str(_("👥 Бэкап пользователей")),
        "btn_favs": str(_("⭐ Бэкап избранного")),
        "btn_movies": str(_("🎬 Бэкап всех фильмов")),
        "btn_restore": str(_("📥 Tiklash (Restore)")),
        "btn_back": str(_("⬅️ Назад")),
    }


async def _restore_type_getter(**kwargs):
    return {
        "title": str(_("📥 Qaysi turdagi ma'lumotlarni tiklamoqchisiz?")),
        "users": str(_("👥 Foydalanuvchilar")),
        "favs": str(_("⭐ Tanlanganlar")),
        "films": str(_("🎬 Filmlar")),
        "series": str(_("📺 Seriallar")),
        "mini": str(_("📽 Epizodli filmlar")),
        "multi_films": str(_("🧸 Multfilmlar")),
        "multi_series": str(_("📺 Mult-seriallar")),
        "multi_mini": str(_("📽 Epizodli multfilmlar")),
        "anime_films": str(_("🏮 Anime filmlar")),
        "anime_series": str(_("📺 Anime seriallar")),
        "anime_mini": str(_("📽 Epizodli animelar")),
        "back": str(_("⬅️ Назад")),
    }


async def on_type_selected(c: CallbackQuery, button: Button, manager: DialogManager):
    manager.dialog_data["restore_type"] = button.widget_id
    await manager.switch_to(BackupSG.restore_file)


async def _restore_file_getter(dialog_manager: DialogManager, **kwargs):
    return {"restore_type": dialog_manager.dialog_data.get("restore_type", "?")}


async def go_restore_type(c: CallbackQuery, button: Button, manager: DialogManager):
    await manager.switch_to(BackupSG.restore_type)


async def go_backup_menu(c: CallbackQuery, button: Button, manager: DialogManager):
    await manager.switch_to(BackupSG.menu)


async def on_restore_file(m: Message, input: MessageInput, manager: DialogManager):
    if not m.document or not m.document.file_name.endswith(".json"):
        await m.answer(
            str(_("❌ Iltimos, faqat .json formatdagi zaxira faylini yuboring."))
        )
        return

    session: AsyncSession = manager.middleware_data["session"]
    queries = BackupQueries(session)
    r_type = manager.dialog_data.get("restore_type")

    # JSON faylni vaqtincha saqlash va o'qish
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        await m.bot.download(m.document, tmp.name)
        async with aiofiles.open(tmp.name, "r", encoding="utf-8") as f:
            content = await f.read()
            try:
                data_list = json.loads(content)
            except Exception:
                await m.answer(
                    str(
                        _(
                            "❌ Faylni o'qishda xatolik yuz berdi. JSON formati noto'g'ri."
                        )
                    )
                )
                return
        os.remove(tmp.name)

    if not isinstance(data_list, list):
        await m.answer(str(_("❌ Noto'g'ri format. JSON ro'yxat bo'lishi kerak.")))
        return

    try:
        if r_type == "r_users":
            await queries.restore_users(data_list)
        elif r_type == "r_favs":
            await queries.restore_favorites(data_list)
        else:
            model_map = {
                "r_films": (FeatureFilm, ["code"]),
                "r_series": (Series, ["code", "season", "series"]),
                "r_mini": (MiniSeries, ["code", "series"]),
                "r_multi_films": (MultiFilmFeature, ["code"]),
                "r_multi_series": (MultiFilmSeries, ["code", "season", "series"]),
                "r_multi_mini": (MultiFilmMiniSeries, ["code", "series"]),
                "r_anime_films": (AnimeFeature, ["code"]),
                "r_anime_series": (AnimeSeries, ["code", "season", "series"]),
                "r_anime_mini": (AnimeMiniSeries, ["code", "series"]),
            }
            if r_type in model_map:
                model, keys = model_map[r_type]
                await queries.restore_records(model, data_list, keys)

        await session.commit()
        await m.answer(
            str(
                _(
                    "✅ Ma'lumotlar muvaffaqiyatli tiklandi! (Faqat yo'q qismlari qo'shildi)"
                )
            )
        )
        await manager.switch_to(BackupSG.menu)
    except Exception as e:
        await m.answer(f"❌ Xatolik yuz berdi: {e}")


backup_dialog = Dialog(
    Window(
        Format("{menu_title}"),
        Button(Format("{btn_users}"), id="bk_users", on_click=on_backup_users),
        Button(Format("{btn_favs}"), id="bk_favs", on_click=on_backup_favorites),
        Button(Format("{btn_movies}"), id="bk_movies", on_click=on_backup_movies),
        Button(Format("{btn_restore}"), id="bk_rest", on_click=go_restore_type),
        Row(Cancel(Format("{btn_back}"), id="back")),
        state=BackupSG.menu,
        getter=_backup_menu_getter,
    ),
    Window(
        Format("{title}"),
        Row(
            Button(Format("{users}"), id="r_users", on_click=on_type_selected),
            Button(Format("{favs}"), id="r_favs", on_click=on_type_selected),
        ),
        Row(
            Button(Format("{films}"), id="r_films", on_click=on_type_selected),
            Button(Format("{series}"), id="r_series", on_click=on_type_selected),
            Button(Format("{mini}"), id="r_mini", on_click=on_type_selected),
        ),
        Row(
            Button(
                Format("{multi_films}"), id="r_multi_films", on_click=on_type_selected
            ),
            Button(
                Format("{multi_series}"), id="r_multi_series", on_click=on_type_selected
            ),
            Button(
                Format("{multi_mini}"), id="r_multi_mini", on_click=on_type_selected
            ),
        ),
        Row(
            Button(
                Format("{anime_films}"), id="r_anime_films", on_click=on_type_selected
            ),
            Button(
                Format("{anime_series}"), id="r_anime_series", on_click=on_type_selected
            ),
            Button(
                Format("{anime_mini}"), id="r_anime_mini", on_click=on_type_selected
            ),
        ),
        Button(Format("{back}"), id="b", on_click=go_backup_menu),
        state=BackupSG.restore_type,
        getter=_restore_type_getter,
    ),
    Window(
        Format(
            "📥 <b>[{restore_type}]</b> ni tiklash.\n\nIltimos, zaxira (.json) faylini yuboring:"
        ),
        MessageInput(on_restore_file, content_types=ContentType.DOCUMENT),
        Button(Format("⬅️ Bekor qilish"), id="b", on_click=go_restore_type),
        state=BackupSG.restore_file,
        getter=_restore_file_getter,
    ),
)
