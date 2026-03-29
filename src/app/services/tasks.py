import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from celery import shared_task

from src.app.bot.common.genres import serialize_genres
from src.app.bot.common.i18n import i18n
from src.app.bot.common.utils import get_lang_code
from src.app.core.config import load_config
from src.app.database.core import Database
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
from src.app.services.transcoder import Transcoder

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  DB SAVE
# ─────────────────────────────────────────────


async def _save_to_db(data: dict, files: dict, is_incremental: bool = False):
    settings = load_config()
    db = Database(settings.construct_postgresql_url())

    async with db.session_factory() as session:
        category = data.get("category")
        movie_type = data.get("movie_type")
        is_adding = data.get("is_adding_track", False)
        lang_id = get_lang_code(data.get("language", "uz"))
        genres_serialized = serialize_genres(data.get("genres") or [])
        thumbnail_id = data.get("thumbnail_file_id")
        code = data.get("code")

        # Normalize category
        cat_map = {"cat_film": "film", "cat_multi": "multi_film", "cat_anime": "anime"}
        category = cat_map.get(category, category)

        # Pre-process name and caption if they are dicts (common when adding track)
        name = data.get("name")
        if isinstance(name, dict):
            name = name.get(lang_id) or next(iter(name.values()), None)
        
        caption = data.get("caption")
        if isinstance(caption, dict):
            caption = caption.get(lang_id) or next(iter(caption.values()), None)

        # Helper to get the right actions class
        from src.app.bot.dialog.admin.edit_movie import get_actions
        actions = get_actions(session, category, movie_type)

        if not actions:
            logger.error(f"Unknown category/type: {category}/{movie_type}")
            return

        # Case 1: Incremental update or adding a new track
        if is_adding or is_incremental:
            if movie_type == "feature_film":
                await actions.update_language_track(
                    code, lang_id, files=files, name=name, caption=caption, thumbnail_file_id=thumbnail_id
                )
            elif movie_type == "series":
                await actions.update_language_track(
                    code, data["season"], data["series"], lang_id, files=files, 
                    name=name, caption=caption, thumbnail_file_id=thumbnail_id
                )
            elif movie_type == "mini_series":
                await actions.update_language_track(
                    code, data["series"], lang_id, files=files, 
                    name=name, caption=caption, thumbnail_file_id=thumbnail_id
                )
        # Case 2: Adding a brand new film (very first quality)
        else:
            if movie_type == "feature_film":
                await actions.add_feature_film(
                    film_code=code, film_name=name, 
                    caption=caption, genres=genres_serialized,
                    language=lang_id, files=files, thumbnail_file_id=thumbnail_id,
                )
            elif movie_type == "series":
                await actions.add_series(
                    series_code=code, series_name=name, series_num=data["series"], season=data["season"],
                    caption=caption, genres=genres_serialized,
                    language=lang_id, files=files, thumbnail_file_id=thumbnail_id
                )
            elif movie_type == "mini_series":
                await actions.add_mini_series(
                    mini_series_code=code, mini_series_name=name, series=data["series"],
                    caption=caption, genres=genres_serialized,
                    language=lang_id, files=files, thumbnail_file_id=thumbnail_id
                )
        
        await session.commit()


# ─────────────────────────────────────────────
#  EDIT: DB UPDATE
# ─────────────────────────────────────────────


async def _update_db_files(data: dict, files: dict):
    """is_editing=True bo'lganda faqat files ni yangilaydi."""
    settings = load_config()
    db = Database(settings.construct_postgresql_url())

    async with db.session_factory() as session:
        category = data.get("category")
        movie_type = data.get("movie_type")
        lang_id = get_lang_code(data.get("language", "uz"))
        code = data.get("code")
        ep_id = data.get("ep_id")

        # Normalize category
        cat_map = {"cat_film": "film", "cat_multi": "multi_film", "cat_anime": "anime"}
        category = cat_map.get(category, category)

        from src.app.bot.dialog.admin.edit_movie import get_actions

        actions = get_actions(session, category, movie_type)

        # Pre-process name and caption if they are dicts 
        name = data.get("name")
        if isinstance(name, dict):
            name = name.get(lang_id)
        
        caption = data.get("caption")
        if isinstance(caption, dict):
            caption = caption.get(lang_id)

        if movie_type == "feature_film":
            await actions.update_language_track(
                code,
                lang_id,
                files=files,
                name=name,
                caption=caption,
                thumbnail_file_id=data.get("thumbnail_file_id")
            )
        elif movie_type == "series" and ep_id:
            s, n = map(int, ep_id.split(":"))
            await actions.update_language_track(
                code,
                s,
                n,
                lang_id,
                files=files,
                name=name,
                caption=caption,
                thumbnail_file_id=data.get("thumbnail_file_id")
            )
        elif movie_type == "mini_series" and ep_id:
            n = int(ep_id)
            await actions.update_language_track(
                code,
                n,
                lang_id,
                files=files,
                name=name,
                caption=caption,
                thumbnail_file_id=data.get("thumbnail_file_id")
            )
        else:
            logger.error(
                f"_update_db_files: ep_id yo'q yoki noto'g'ri tip: {movie_type}"
            )
            raise ValueError("ep_id required for series/mini_series update")

        await session.commit()


# ─────────────────────────────────────────────
#  CELERY TASK
# ─────────────────────────────────────────────


@shared_task(
    name="src.app.services.tasks.process_video_task",
    bind=True,
    max_retries=0,
)
def process_video_task(self, data: dict):
    try:
        return asyncio.run(_run_task(data))
    except Exception as exc:
        logger.error(f"Task failed: {exc}", exc_info=True)
        raise


async def _run_task(data: dict):
    settings = load_config()

    # BUG FIX #4: session yaratishda timeout juda kam edi
    # Katta fayllar uchun 3600s kerak
    session = AiohttpSession(
        api=TelegramAPIServer.from_base(settings.tg_api_server_url),
        timeout=3600,
    )

    async with Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode="HTML"),
    ) as bot:
        transcoder = Transcoder(bot)
        user_id = data.get("admin_id")
        status_msg_id = data.get("status_msg_id")
        admin_locale = data.get("admin_locale") or "uz"

        async def update_status(text: str):
            if status_msg_id and user_id:
                try:
                    await bot.edit_message_text(
                        chat_id=user_id,
                        message_id=status_msg_id,
                        text=text,
                    )
                except Exception:
                    pass

        ready_files = {}

        async def on_quality_ready(quality: str, file_id: str):
            is_first = (len(ready_files) == 0)
            ready_files[quality] = file_id
            try:
                # Use partial files dict for incremental update
                partial = {quality: file_id}
                if data.get("is_editing"):
                    await _update_db_files(data, partial)
                else:
                    # Har bir sifat tayyor bo'lganda incremental saqlaymiz.
                    # Birinchi sifat bo'lganda add_..., qolganlarida update_...
                    await _save_to_db(data, partial, is_incremental=not is_first)
                logger.info(f"Incremental save done: {quality}")
            except Exception as e:
                logger.error(f"Incremental save failed for {quality}: {e}")

        cleanup_list = []

        async def _cleanup_local_api_cache(paths: list):
            """Local API server keshini jarrohlik yo'li bilan tozalash"""
            try:
                import os
                for path in paths:
                    if os.path.exists(path):
                        os.remove(path)
                        logger.info(f"Surgical cleanup: {path}")
            except Exception as e:
                logger.warning(f"Cleanup failed: {e}")

        try:
            files, cleanup_list = await transcoder.process_video(
                file_id=data.get("file_id"),
                user_id=user_id,
                status_callback=update_status,
                on_quality_ready=on_quality_ready,
                thumbnail_file_id=data.get("thumbnail_file_id"),
                locale=admin_locale,
            )

            if not files or not isinstance(files, dict):
                raise ValueError("Transcoder bo'sh natija qaytardi")

            success_msg = i18n.gettext(
                "✅ Video muvaffaqiyatli saqlandi! Kod: {code}",
                locale=admin_locale,
            ).format(code=data.get("code"))

            await bot.send_message(chat_id=user_id, text=success_msg)
            return files

        except Exception as e:
            logger.error(f"Task run failed: {e}", exc_info=True)
            if user_id:
                try:
                    error_text = i18n.gettext(
                        "❌ Xato: {error}", locale=admin_locale
                    ).format(error=str(e)[:200])
                    await bot.send_message(chat_id=user_id, text=error_text)
                except Exception:
                    pass
            raise
        finally:
            await _cleanup_local_api_cache(cleanup_list)
