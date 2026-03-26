import asyncio
import datetime
import json
import os
import tempfile

import aiofiles
from aiogram.types import CallbackQuery, FSInputFile
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Button, Cancel, Row
from aiogram_dialog.widgets.text import Format
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.common.i18n import lazy_gettext as _
from src.app.bot.states.admin.dialogs import BackupSG
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
            "video_file_id": f.video_file_id,
            "captions": f.captions,
            "genres": f.genres,
            "format": f.format,
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
            "video_file_id": s.video_file_id,
            "captions": s.captions,
            "genres": s.genres,
            "format": s.format,
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
            "video_file_id": m.video_file_id,
            "captions": m.captions,
            "genres": m.genres,
            "format": m.format,
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


# ─── MUAMMO BU YERDA EDI ────────────────────────────────────────────────────
#
# XATO:   Const(str(_("matni")))
#          └─ str() lazy_gettext'ni darhol bajaradi → bot start bo'lganida,
#             foydalanuvchi tili yo'q → default "uz" ishlatiladi, hech qachon
#             o'zgarmaydi.
#
# TO'G'RI: Format("{text}") + getter orqali yoki shunchaki
#          aiogram-dialog'ning o18n integratsiyasidan foydalanish.
#
#  Eng sodda yechim — Const ichida lazy string'ni str() ga O'RAMASLIK va
#  I18NFormat widgetini ishlatish (agar o'rnatilgan bo'lsa), yoki quyidagi
#  kabi getter bilan Format ishlatish.
# ────────────────────────────────────────────────────────────────────────────


async def _backup_menu_getter(**kwargs):
    return {
        "menu_title": str(
            _("💾 <b>Меню бэкапа</b>\n\nВыберите тип данных для выгрузки:")
        ),
        "btn_users": str(_("👥 Бэкап пользователей")),
        "btn_favs": str(_("⭐ Бэкап избранного")),
        "btn_movies": str(_("🎬 Бэкап всех фильмов")),
        "btn_back": str(_("⬅️ Назад")),
    }


backup_dialog = Dialog(
    Window(
        Format("{menu_title}"),
        Button(
            Format("{btn_users}"),
            id="bk_users",
            on_click=on_backup_users,
        ),
        Button(
            Format("{btn_favs}"),
            id="bk_favs",
            on_click=on_backup_favorites,
        ),
        Button(
            Format("{btn_movies}"),
            id="bk_movies",
            on_click=on_backup_movies,
        ),
        Row(
            Cancel(Format("{btn_back}"), id="back"),
        ),
        state=BackupSG.menu,
        getter=_backup_menu_getter,
    )
)
