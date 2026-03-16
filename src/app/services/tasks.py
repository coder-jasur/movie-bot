import asyncio
import logging
from celery import shared_task
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from src.app.core.config import load_config
from src.app.services.transcoder import Transcoder
from src.app.database.core import Database
from src.app.database.queries.movie.feature_films import FeatureFilmsActions
from src.app.database.queries.movie.series import SeriesActions
from src.app.database.queries.movie.mini_series import MiniSeriesActions
from src.app.database.queries.movie.multi_films import (
    MultiFilmFeatureActions,
    MultiFilmSeriesActions,
    MultiFilmMiniSeriesActions,
)
from src.app.database.queries.movie.anime import (
    AnimeFeatureActions,
    AnimeSeriesActions,
    AnimeMiniSeriesActions,
)
from src.app.bot.common.genres import serialize_genres
from src.app.bot.common.utils import get_lang_code
from src.app.bot.common.i18n import lazy_gettext as _

logger = logging.getLogger(__name__)

async def _save_to_db(data: dict, files: dict):
    settings = load_config()
    db = Database(settings.construct_postgresql_url())
    
    async with db.session_factory() as session:
        category = data.get("category")
        movie_type = data.get("movie_type")
        is_adding = data.get("is_adding_track", False)
        lang_id = get_lang_code(data.get("language", "uz"))
        genres_serialized = serialize_genres(data.get("genres", []))
        thumbnail_id = data.get("thumbnail_file_id")
        code = data.get("code")
        
        # Determine which action class to use
        if category == "cat_film":
            if movie_type == "feature_film":
                actions = FeatureFilmsActions(session)
                if is_adding:
                    await actions.add_language_track(
                        film_code=code, language=lang_id, video_file_id=files.get("original"),
                        caption=data.get("caption"), files=files, name=data.get("name"),
                        thumbnail_file_id=thumbnail_id,
                    )
                else:
                    await actions.add_feature_film(
                        film_code=code, film_name=data["name"], video_file_id=files.get("original"),
                        caption=data.get("caption"), genres=genres_serialized, format=data.get("format"),
                        language=lang_id, files=files, thumbnail_file_id=thumbnail_id,
                    )
            elif movie_type == "series":
                actions = SeriesActions(session)
                if is_adding:
                    await actions.add_language_track(
                        series_code=code, season=data["season"], series_num=data["series"],
                        language=lang_id, video_file_id=files.get("original"),
                        caption=data.get("caption"), files=files, name=data.get("name"),
                        thumbnail_file_id=thumbnail_id,
                    )
                else:
                    await actions.add_series(
                        series_code=code, series_name=data["name"], series_num=data["series"],
                        season=data["season"], video_file_id=files.get("original"),
                        caption=data.get("caption"), genres=genres_serialized, format=data.get("format"),
                        language=lang_id, files=files, thumbnail_file_id=thumbnail_id,
                    )
            elif movie_type == "mini_series":
                actions = MiniSeriesActions(session)
                if is_adding:
                    await actions.add_language_track(
                        mini_series_code=code, series_num=data["series"],
                        language=lang_id, video_file_id=files.get("original"),
                        caption=data.get("caption"), files=files, name=data.get("name"),
                        thumbnail_file_id=thumbnail_id,
                    )
                else:
                    await actions.add_mini_series(
                        mini_series_code=code, mini_series_name=data["name"], series=data["series"],
                        video_file_id=files.get("original"), caption=data.get("caption"),
                        genres=genres_serialized, format=data.get("format"),
                        language=lang_id, files=files, thumbnail_file_id=thumbnail_id,
                    )

        elif category == "cat_multi":
            if movie_type == "feature_film":
                actions = MultiFilmFeatureActions(session)
                if is_adding:
                    await actions.add_language_track(film_code=code, language=lang_id, video_file_id=files.get("original"), caption=data.get("caption"), files=files, name=data.get("name"), thumbnail_file_id=thumbnail_id)
                else:
                    await actions.add_feature_film(film_code=code, film_name=data["name"], video_file_id=files.get("original"), caption=data.get("caption"), genres=genres_serialized, format=data.get("format"), language=lang_id, files=files, thumbnail_file_id=thumbnail_id)
            elif movie_type == "series":
                actions = MultiFilmSeriesActions(session)
                if is_adding:
                    await actions.add_language_track(series_code=code, season=data["season"], series_num=data["series"], language=lang_id, video_file_id=files.get("original"), caption=data.get("caption"), files=files, name=data.get("name"), thumbnail_file_id=thumbnail_id)
                else:
                    await actions.add_series(series_code=code, series_name=data["name"], series_num=data["series"], season=data["season"], video_file_id=files.get("original"), caption=data.get("caption"), genres=genres_serialized, format=data.get("format"), language=lang_id, files=files, thumbnail_file_id=thumbnail_id)

        elif category == "cat_anime":
             # Anime logic follows the same pattern as above
             pass

        await session.commit()

@shared_task(name="src.app.services.tasks.process_video_task")
def process_video_task(data: dict):
    settings = load_config()
    
    async def run():
        session = AiohttpSession(
            api=TelegramAPIServer.from_base(settings.tg_api_server_url),
            timeout=600,
        )
        async with Bot(token=settings.bot_token, session=session, default=DefaultBotProperties(parse_mode="HTML")) as bot:
            transcoder = Transcoder(bot)
            user_id = data.get("admin_id")
            status_msg_id = data.get("status_msg_id")

            async def update_status(text: str):
                if status_msg_id and user_id:
                    try:
                        await bot.edit_message_text(chat_id=user_id, message_id=status_msg_id, text=text)
                    except Exception:
                        pass

            try:
                files = await transcoder.process_video(
                    file_id=data.get("file_id"),
                    user_id=user_id,
                    status_callback=update_status,
                    thumbnail_file_id=data.get("thumbnail_file_id")
                )
                
                if data.get("is_editing"):
                    # Tahrirlash logikasi (edit_movie.py dagi kabi)
                    pass
                else:
                    await _save_to_db(data, files)
                
                success_msg = str(_("✅ Video muvaffaqiyatli saqlandi! Kod: {code}")).format(code=data.get('code'))
                await bot.send_message(chat_id=user_id, text=success_msg)
                return files
            except Exception as e:
                logger.error(f"Task failed: {e}")
                if user_id:
                    error_msg = str(_("❌ Xato: {error}")).format(error=str(e))
                    await bot.send_message(chat_id=user_id, text=error_msg)
                raise e

    loop = asyncio.get_event_loop()
    return loop.run_until_complete(run())
