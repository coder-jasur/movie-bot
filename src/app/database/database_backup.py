import asyncio
import datetime
import logging
import os

import aiofiles
from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy.ext.asyncio import async_sessionmaker

import zipfile

from src.app.database.queries.backup import BackupQueries

logger = logging.getLogger(__name__)


async def send_database_to_owner(bot: Bot, chat_ids: list[int], db_path: str):
    is_file_exists = await asyncio.to_thread(os.path.exists, db_path)

    if is_file_exists:
        db_file = FSInputFile(db_path)
        tasks = [
            asyncio.create_task(
                bot.send_document(
                    chat_id=chat_id, document=db_file, caption="📦 База Данных"
                )
            )
            for chat_id in chat_ids
        ]
        await asyncio.gather(*tasks)


async def _write_json(path: str, data: list | dict) -> None:
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        import json
        await f.write(json.dumps(data, ensure_ascii=False, indent=4))

async def daily_database_sender(
    bot: Bot, chat_ids: list[int], session_pool: async_sessionmaker
) -> None:
    while True:
        try:
            now = datetime.datetime.now()
            target_time = now.replace(hour=0, minute=0, second=0, microsecond=0)

            if now >= target_time:
                target_time += datetime.timedelta(days=1)

            sleep_duration = (target_time - now).total_seconds()
            await asyncio.sleep(sleep_duration)

            # Dump everything
            async with session_pool() as session:
                queries = BackupQueries(session)
                
                # 1. Users
                users = await queries.get_all_users()
                users_data = [
                    {
                        "tg_id": u.tg_id, "username": u.username, "status": u.status,
                        "language_code": u.language_code, "is_premium": u.is_premium,
                        "vip_status": u.vip_status, "vip_payment_history": u.vip_payment_history,
                        "vip_expires_at": u.vip_expires_at.isoformat() if u.vip_expires_at else None,
                        "referral_url": u.referral_url, "joined_count": u.joined_count,
                        "created_at": u.created_at.isoformat() if u.created_at else None
                    } for u in users
                ]

                # 2. Favorites
                favs = await queries.get_all_favorites()
                favs_data = [
                    {
                        "user_id": f.user_id, "movie_code": f.movie_code,
                        "created_at": f.created_at.isoformat() if f.created_at else None
                    } for f in favs
                ]

                # 3. Systems
                channels = await queries.get_all_channels()
                bots = await queries.get_all_bots()
                urls = await queries.get_all_sub_urls()
                referrals = await queries.get_all_referrals()
                sys_data = {
                    "channels": [
                        {"channel_id": x.channel_id, "channel_name": x.channel_name, "channel_username": x.channel_username, "channel_status": x.channel_status, "message": x.message, "channel_url": x.channel_url, "created_at": x.created_at.isoformat() if x.created_at else None} for x in channels
                    ],
                    "bots": [
                        {"bot_username": x.bot_username, "bot_name": x.bot_name, "bot_status": x.bot_status, "bot_url": x.bot_url, "created_at": x.created_at.isoformat() if x.created_at else None} for x in bots
                    ],
                    "urls": [
                        {"url_id": x.url_id, "url_name": x.url_name, "url_link": x.url_link, "url_status": x.url_status,  "created_at": x.created_at.isoformat() if x.created_at else None} for x in urls
                    ],
                    "referrals": [
                        {"referral_id": x.referral_id, "name": x.name, "joined_count": x.joined_count, "created_at": x.created_at.isoformat() if x.created_at else None} for x in referrals
                    ]
                }

                # 4. Movies
                def _film_row(f):
                    return {"code": f.code,"name": f.name,"captions": f.captions,"genres": f.genres,"language": f.language,"files": f.files,"thumbnails": f.thumbnails,"views_count": f.views_count,}
                def _series_row(s):
                    return {"code": s.code,"season": s.season,"series": s.series,"name": s.name,"captions": s.captions,"genres": s.genres,"language": s.language,"files": s.files,"thumbnails": s.thumbnails,"views_count": s.views_count,}
                def _mini_row(m):
                    return {"code": m.code,"series": m.series,"name": m.name,"captions": m.captions,"genres": m.genres,"language": m.language,"files": m.files,"thumbnails": m.thumbnails,"views_count": m.views_count,}
                
                movies = {
                    "feature_films": [_film_row(r) for r in await queries.get_all_feature_films()],
                    "series": [_series_row(r) for r in await queries.get_all_series()],
                    "mini_series": [_mini_row(r) for r in await queries.get_all_mini_series()],
                    "multi_film_features": [_film_row(r) for r in await queries.get_all_multi_film_features()],
                    "multi_film_series": [_series_row(r) for r in await queries.get_all_multi_film_series()],
                    "multi_film_mini_series": [_mini_row(r) for r in await queries.get_all_multi_film_mini_series()],
                    "anime_features": [_film_row(r) for r in await queries.get_all_anime_features()],
                    "anime_series": [_series_row(r) for r in await queries.get_all_anime_series()],
                    "anime_mini_series": [_mini_row(r) for r in await queries.get_all_anime_mini_series()]
                }

            # Write to disk and zip
            today_str = datetime.date.today().isoformat()
            zip_filename = f"db_backup_full_{today_str}.zip"

            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                u_path = os.path.join(tmpdir, f"users_backup_{today_str}.json")
                await _write_json(u_path, users_data)
                
                f_path = os.path.join(tmpdir, f"favorites_backup_{today_str}.json")
                await _write_json(f_path, favs_data)
                
                s_path = os.path.join(tmpdir, f"systems_backup_{today_str}.json")
                await _write_json(s_path, sys_data)
                
                m_paths = []
                for m_name, m_data in movies.items():
                    m_path = os.path.join(tmpdir, f"backup_{m_name}_{today_str}.json")
                    await _write_json(m_path, m_data)
                    m_paths.append(m_path)

                zip_filepath = os.path.join(tmpdir, zip_filename)
                
                def _make_zip():
                    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                        zf.write(u_path, os.path.basename(u_path))
                        zf.write(f_path, os.path.basename(f_path))
                        zf.write(s_path, os.path.basename(s_path))
                        for mp in m_paths:
                            zf.write(mp, os.path.basename(mp))
                
                await asyncio.to_thread(_make_zip)
                await send_database_to_owner(bot, chat_ids, zip_filepath)

        except Exception as e:
            logger.exception(e)
            await asyncio.sleep(60)
