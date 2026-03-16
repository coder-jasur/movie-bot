import asyncio
import json
import datetime
import os
import aiofiles
from aiogram.types import CallbackQuery, FSInputFile
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.kbd import Button, Row, Cancel
from aiogram_dialog.widgets.text import Const
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.states.admin.dialogs import BackupSG
from src.app.database.queries.backup import BackupQueries
from src.app.bot.common.i18n import lazy_gettext as _

async def on_backup_users(c: CallbackQuery, button: Button, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    queries = BackupQueries(session)
    users = await queries.get_all_users()
    
    data = []
    for user in users:
        data.append({
            "tg_id": user.tg_id,
            "username": user.username,
            "status": user.status,
            "language_code": user.language_code,
            "is_premium": user.is_premium,
            "created_at": user.created_at.isoformat() if user.created_at else None
        })
    
    filename = f"users_backup_{datetime.date.today()}.json"
    async with aiofiles.open(filename, "w", encoding="utf-8") as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=4))
    
    await c.message.answer_document(
        FSInputFile(filename),
        caption=str(_("📁 Полный бэкап ВСЕХ пользователей"))
    )
    # Proactive cleanup
    if await asyncio.to_thread(os.path.exists, filename):
        await asyncio.to_thread(os.remove, filename)

async def on_backup_favorites(c: CallbackQuery, button: Button, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    queries = BackupQueries(session)
    favorites = await queries.get_all_favorites()
    
    data = [{
        "user_id": f.user_id,
        "movie_code": f.movie_code,
        "created_at": f.created_at.isoformat() if f.created_at else None
    } for f in favorites]
    
    filename = f"favorites_backup_{datetime.date.today()}.json"
    async with aiofiles.open(filename, "w", encoding="utf-8") as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=4))
        
    await c.message.answer_document(
        FSInputFile(filename),
        caption=str(_("📂 Полный бэкап списка Избранного"))
    )
    
    if await asyncio.to_thread(os.path.exists, filename):
        await asyncio.to_thread(os.remove, filename)

async def on_backup_movies(c: CallbackQuery, button: Button, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    queries = BackupQueries(session)
    today = datetime.date.today()
    
    # FILM Category
    films = await queries.get_all_feature_films()
    films_data = [{
        "code": f.code, "name": f.name, "video_file_id": f.video_file_id,
        "captions": f.captions, "genres": f.genres, "views_count": f.views_count
    } for f in films]
    films_file = f"backup_feature_films_{today}.json"
    async with aiofiles.open(films_file, "w", encoding="utf-8") as f:
        await f.write(json.dumps(films_data, ensure_ascii=False, indent=4))
    
    series = await queries.get_all_series()
    series_data = [{
        "code": s.code, "season": s.season, "series": s.series, "name": s.name,
        "video_file_id": s.video_file_id, "captions": s.captions, "genres": s.genres,
        "views_count": s.views_count
    } for s in series]
    series_file = f"backup_series_{today}.json"
    async with aiofiles.open(series_file, "w", encoding="utf-8") as f:
        await f.write(json.dumps(series_data, ensure_ascii=False, indent=4))
        
    mini = await queries.get_all_mini_series()
    mini_data = [{
        "code": m.code, "series": m.series, "name": m.name, "video_file_id": m.video_file_id,
        "captions": m.captions, "genres": m.genres, "views_count": m.views_count
    } for m in mini]
    mini_file = f"backup_mini_series_{today}.json"
    async with aiofiles.open(mini_file, "w", encoding="utf-8") as f:
        await f.write(json.dumps(mini_data, ensure_ascii=False, indent=4))
    
    # MULTI-FILM Category
    multi_films = await queries.get_all_multi_film_features()
    multi_films_data = [{
        "code": f.code, "name": f.name, "video_file_id": f.video_file_id,
        "captions": f.captions, "genres": f.genres, "views_count": f.views_count
    } for f in multi_films]
    multi_films_file = f"backup_multi_film_features_{today}.json"
    async with aiofiles.open(multi_films_file, "w", encoding="utf-8") as f:
        await f.write(json.dumps(multi_films_data, ensure_ascii=False, indent=4))
    
    multi_series = await queries.get_all_multi_film_series()
    multi_series_data = [{
        "code": s.code, "season": s.season, "series": s.series, "name": s.name,
        "video_file_id": s.video_file_id, "captions": s.captions, "genres": s.genres,
        "views_count": s.views_count
    } for s in multi_series]
    multi_series_file = f"backup_multi_film_series_{today}.json"
    async with aiofiles.open(multi_series_file, "w", encoding="utf-8") as f:
        await f.write(json.dumps(multi_series_data, ensure_ascii=False, indent=4))
    
    multi_mini = await queries.get_all_multi_film_mini_series()
    multi_mini_data = [{
        "code": m.code, "series": m.series, "name": m.name, "video_file_id": m.video_file_id,
        "captions": m.captions, "genres": m.genres, "views_count": m.views_count
    } for m in multi_mini]
    multi_mini_file = f"backup_multi_film_mini_series_{today}.json"
    async with aiofiles.open(multi_mini_file, "w", encoding="utf-8") as f:
        await f.write(json.dumps(multi_mini_data, ensure_ascii=False, indent=4))
    
    # ANIME Category
    anime_films = await queries.get_all_anime_features()
    anime_films_data = [{
        "code": f.code, "name": f.name, "video_file_id": f.video_file_id,
        "captions": f.captions, "genres": f.genres, "views_count": f.views_count
    } for f in anime_films]
    anime_films_file = f"backup_anime_features_{today}.json"
    async with aiofiles.open(anime_films_file, "w", encoding="utf-8") as f:
        await f.write(json.dumps(anime_films_data, ensure_ascii=False, indent=4))
    
    anime_series = await queries.get_all_anime_series()
    anime_series_data = [{
        "code": s.code, "season": s.season, "series": s.series, "name": s.name,
        "video_file_id": s.video_file_id, "captions": s.captions, "genres": s.genres,
        "views_count": s.views_count
    } for s in anime_series]
    anime_series_file = f"backup_anime_series_{today}.json"
    async with aiofiles.open(anime_series_file, "w", encoding="utf-8") as f:
        await f.write(json.dumps(anime_series_data, ensure_ascii=False, indent=4))
    
    anime_mini = await queries.get_all_anime_mini_series()
    anime_mini_data = [{
        "code": m.code, "series": m.series, "name": m.name, "video_file_id": m.video_file_id,
        "captions": m.captions, "genres": m.genres, "views_count": m.views_count
    } for m in anime_mini]
    anime_mini_file = f"backup_anime_mini_series_{today}.json"
    async with aiofiles.open(anime_mini_file, "w", encoding="utf-8") as f:
        await f.write(json.dumps(anime_mini_data, ensure_ascii=False, indent=4))
        
    # Send all files
    await c.message.answer_document(FSInputFile(films_file), caption=str(_("🎬 BBARCHA filmlarning to'liq zaxirasi")))
    await c.message.answer_document(FSInputFile(series_file), caption=str(_("📺 BARCHA seriallarning to'liq zaxirasi")))
    await c.message.answer_document(FSInputFile(mini_file), caption=str(_("📽 BARCHA epizodli filmlarning to'liq zaxirasi")))
    
    await c.message.answer_document(FSInputFile(multi_films_file), caption=str(_("🧸 BARCHA multfilmlarning to'liq zaxirasi")))
    await c.message.answer_document(FSInputFile(multi_series_file), caption=str(_("📺 BARCHA mult-seriallarning to'liq zaxirasi")))
    await c.message.answer_document(FSInputFile(multi_mini_file), caption=str(_("📽 BARCHA epizodli multfilmlarning to'liq zaxirasi")))
    
    await c.message.answer_document(FSInputFile(anime_films_file), caption=str(_("🏮 BARCHA anime filmlarning to'liq zaxirasi")))
    await c.message.answer_document(FSInputFile(anime_series_file), caption=str(_("📺 BARCHA anime seriallarning to'liq zaxirasi")))
    await c.message.answer_document(FSInputFile(anime_mini_file), caption=str(_("📽 BARCHA epizodli animelarning to'liq zaxirasi")))

    # Cleanup
    for f in [films_file, series_file, mini_file, multi_films_file, multi_series_file, 
              multi_mini_file, anime_films_file, anime_series_file, anime_mini_file]:
        if await asyncio.to_thread(os.path.exists, f):
            await asyncio.to_thread(os.remove, f)

backup_dialog = Dialog(
    Window(
        Const(str(_("💾 <b>Меню бэкапа</b>\n\nВыберите тип данных для выгрузки:"))),
        Button(Const(str(_("👥 Бэкап пользователей"))), id="bk_users", on_click=on_backup_users),
        Button(Const(str(_("⭐ Бэкап избранного"))), id="bk_favs", on_click=on_backup_favorites),
        Button(Const(str(_("🎬 Бэкап всех фильмов"))), id="bk_movies", on_click=on_backup_movies),
        Row(
            Cancel(Const(str(_("⬅️ Назад"))), id="back"),
        ),
        state=BackupSG.menu,
    )
)
