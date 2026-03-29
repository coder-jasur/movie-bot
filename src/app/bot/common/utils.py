import json
import logging
from datetime import datetime, timedelta
from contextlib import suppress

from aiogram.types import BufferedInputFile, FSInputFile, User
from aiogram.types import InputMediaPhoto, InputMediaVideo
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def get_thumbnail_input(bot, file_id: str):
    """
    Given a Telegram file_id for a photo/thumbnail, return an InputFile
    that aiogram v3 (Pydantic v2) accepts as the `thumbnail` argument.
    """
    if not file_id:
        logger.debug("get_thumbnail_input: no file_id, skipping")
        return None
    try:
        import asyncio
        import os
        import tempfile

        logger.debug(f"get_thumbnail_input: starting for {file_id[:20]}...")

        file_info = await bot.get_file(file_id)
        file_path = file_info.file_path

        # 1. Resolve source path
        source_path = None
        local_base = "/var/lib/telegram-bot-api"
        token = bot.token

        if os.path.isfile(file_path):
            source_path = file_path
        else:
            abs_path1 = os.path.join(local_base, token, file_path.lstrip("/"))
            if os.path.isfile(abs_path1):
                source_path = abs_path1
            else:
                abs_path2 = os.path.join(local_base, file_path.lstrip("/"))
                if os.path.isfile(abs_path2):
                    source_path = abs_path2

        # 2. Download if not local.
        temp_dir = "/var/lib/telegram-bot-api/temp"
        os.makedirs(temp_dir, exist_ok=True)
        download_path = os.path.join(temp_dir, f"raw_thumb_{file_id[-10:]}.jpg")

        if not source_path:
            await bot.download_file(file_path, destination=download_path)
            source_path = download_path
            logger.debug(f"get_thumbnail_input: downloaded to {source_path}")

        # 3. Apply Watermark
        base_dir = "/app"
        watermark_path = os.path.join(base_dir, "media/photos/bot_watermark.png")

        if os.path.exists(watermark_path):
            output_path = os.path.join(temp_dir, f"wm_thumb_{file_id[-10:]}.jpg")
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                source_path,
                "-i",
                watermark_path,
                "-filter_complex",
                (
                    f"[1:v]scale=iw/4:-1[wm];"
                    f"[0:v][wm]overlay=W-w-10:10[base];"
                    f"[base]scale=320:320:force_original_aspect_ratio=decrease"
                ),
                output_path,
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if proc.returncode == 0:
                    return FSInputFile(output_path, filename="thumbnail.jpg")
            except Exception:
                pass

        return FSInputFile(source_path, filename="thumbnail.jpg")

    except Exception as e:
        logger.warning(f"get_thumbnail_input failed: {e}")
        return None


def get_tashkent_time():
    return datetime.utcnow() + timedelta(hours=5)


async def is_active_vip(user, session: AsyncSession = None) -> bool:
    if not user: return False
    from src.app.core.config import load_config
    config = load_config()
    if user.tg_id in config.admins_ids: return True
    if session:
        from src.app.database.queries.admin import AdminActions
        if await AdminActions(session).is_admin(user.tg_id): return True
    if user.vip_status != "active": return False
    if not user.vip_expires_at: return True
    return user.vip_expires_at > get_tashkent_time()


async def get_user_language(user: User, session: AsyncSession = None) -> str:
    if session:
        from src.app.database.queries.user import UserActions
        db_user = await UserActions(session).get_user(user.id)
        if db_user and db_user.language_code:
            return get_lang_code(db_user.language_code)
    lang = user.language_code
    return get_lang_code(lang) if lang else "uz"


def deep_parse_json(data):
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, (dict, list)):
                return deep_parse_json(parsed)
            return parsed
        except:
            return data
    if isinstance(data, dict):
        return {k: deep_parse_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [deep_parse_json(v) for v in data]
    return data


def deep_flatten_name(obj, depth=0):
    if depth > 15: return obj
    if isinstance(obj, str):
        stripped = obj.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or (
            stripped.startswith("[") and stripped.endswith("]")
        ):
            try:
                parsed = json.loads(obj)
                if parsed != obj: return deep_flatten_name(parsed, depth + 1)
            except: pass
        return obj
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            nk = get_lang_code(k)
            flat_v = deep_flatten_name(v, depth + 1)
            if isinstance(flat_v, dict):
                for ik, iv in flat_v.items():
                    ik_norm = get_lang_code(ik)
                    if ik_norm == nk or ik_norm not in result:
                        result[ik_norm] = deep_flatten_name(iv, depth + 1)
            else:
                if nk not in result or not result[nk]:
                    result[nk] = flat_v
        return result
    if isinstance(obj, list) and obj:
        return deep_flatten_name(obj[0], depth + 1)
    return obj


def get_lang_code(label: str) -> str:
    if not label: return "uz"
    l = str(label).lower()
    if "o'zbek" in l or "uz" in l: return "uz"
    if "rus" in l or "ru" in l: return "ru"
    if "ingliz" in l or "en" in l or "english" in l: return "en"
    return l


def build_movie_caption(movie, lang: str) -> str:
    from src.app.bot.common.genres import deserialize_genres, get_genre_display_text
    from src.app.bot.common.i18n import i18n
    lang = get_lang_code(lang)
    _l = lambda x: i18n.gettext(x, locale=lang)
    icon = "📺" if "series" in movie.__class__.__name__.lower() else "🎬"
    if "mini" in movie.__class__.__name__.lower(): icon = "🧩"
    genres = getattr(movie, "genres", "[]")
    genres_text = get_genre_display_text(deserialize_genres(genres), lang=lang)
    code = getattr(movie, "code", "????")
    name = get_localized_name(movie, lang)
    ep_info = ""
    if hasattr(movie, "series"):
        if hasattr(movie, "season"):
            ep_info = f"\n└ 📅 {_l('Mavsum')}: <b>{movie.season}</b>, {_l('Qism')}: <b>{movie.series}</b>"
        else:
            ep_info = f"\n└ 🔢 {_l('Qism')}: <b>{movie.series}</b>"
    return (
        f"{icon} <b>{name}</b>\n"
        f"└ 🎭 {_l('Janr')}: <b>{genres_text}</b>\n"
        f"└ 🆔 {_l('Kod')}: <code>{code}</code>"
        f"{ep_info}"
    )


def resolve_movie_media(
    movie, user_lang: str, pref_quality: str = None, is_vip: bool = False
):
    """
    Standardized video/caption/thumbnail selection logic.
    Exclusively uses 'files', 'captions', 'thumbnails' columns.
    """
    # 1. Parse JSON
    files = deep_parse_json(movie.files) or {}
    captions = deep_parse_json(movie.captions) or {}
    thumbnails = deep_parse_json(movie.thumbnails) or {}

    # 2. Normalize Files to {"uz": {"1080p": "id", ...}, ...}
    normalized_files = {}
    if isinstance(files, dict):
        # Check if flat (qualities at root)
        is_flat = any(str(k).lower().endswith("p") for k in files.keys())
        if is_flat:
            db_lang = getattr(movie, "language", "uz").split(",")[0].strip() or "uz"
            files = {get_lang_code(db_lang): files}
        
        for lang_key, content in files.items():
            short_lang = get_lang_code(lang_key)
            if isinstance(content, str): content = {"original": content}
            if short_lang not in normalized_files: normalized_files[short_lang] = {}
            if isinstance(content, dict): normalized_files[short_lang].update(content)
    files = normalized_files

    # 3. Select Target Language
    user_lang = get_lang_code(user_lang)
    target_lang = user_lang if user_lang in files else None
    if not target_lang:
        from src.app.bot.common.languages import LANGUAGES
        for l in [lang["id"] for lang in LANGUAGES]:
            if l in files: target_lang = l; break
    if not target_lang and files: target_lang = list(files.keys())[0]

    if not target_lang:
        # No files at all
        return None, get_localized_name(movie, user_lang), build_movie_caption(movie, user_lang), user_lang, None, {}, {}, None

    lang_files = files.get(target_lang, {})
    
    # helper for quality ranking
    def get_quality_rank(q: str) -> int:
        q_clean = str(q).lower().strip()
        if q_clean == "original": return 9999
        if q_clean.endswith("p"):
            with suppress(Exception): return int(q_clean[:-1])
        return 0

    # 4. Select Quality
    target_quality = None
    available_ranks = sorted([(q, get_quality_rank(q)) for q in lang_files.keys()], key=lambda x: x[1], reverse=True)

    if pref_quality and pref_quality in lang_files:
        target_quality = pref_quality
    elif available_ranks:
        if is_vip:
            # VIP: Highest numeric quality, or original if only original exists
            target_quality = available_ranks[0][0]
        else:
            # Non-VIP: Best quality < 480p
            non_vip = [x for x in available_ranks if 0 < x[1] < 480]
            target_quality = non_vip[0][0] if non_vip else None

    file_id = lang_files.get(target_quality) if target_quality else None

    # 5. Resolve Name & Caption
    final_name = get_localized_name(movie, user_lang)
    
    # Normalize captions
    flat_captions = {}
    if isinstance(captions, dict):
        for k, v in captions.items():
            if isinstance(v, dict):
                v = next((val for val in v.values() if isinstance(val, str)), str(v))
            flat_captions[get_lang_code(k)] = v
    
    final_caption = flat_captions.get(user_lang)
    if not final_caption: final_caption = flat_captions.get(target_lang)
    if not final_caption and flat_captions:
        final_caption = next((v for v in flat_captions.values() if isinstance(v, str) and v.strip()), None)
    if not final_caption: final_caption = build_movie_caption(movie, user_lang)

    # 6. Resolve Thumbnail
    flat_thumbnails = {get_lang_code(k): v for k, v in thumbnails.items() if isinstance(v, str)} if isinstance(thumbnails, dict) else {}
    thumbnail_id = flat_thumbnails.get(user_lang) or flat_thumbnails.get(target_lang)
    if not thumbnail_id and flat_thumbnails: thumbnail_id = next(iter(flat_thumbnails.values()))

    return file_id, str(final_name), str(final_caption), target_lang, target_quality, files, flat_captions, thumbnail_id


def get_localized_name(movie, user_lang: str) -> str:
    from src.app.bot.common.utils import get_lang_code
    data = getattr(movie, "name", movie.get("name") if isinstance(movie, dict) else movie)
    raw_names = deep_flatten_name(data)
    if isinstance(raw_names, str): return raw_names
    if not isinstance(raw_names, dict): return str(raw_names) if raw_names else "No Name"
    user_lang = get_lang_code(user_lang)
    name = raw_names.get(user_lang) or raw_names.get("uz")
    if not name:
        for v in raw_names.values():
            if isinstance(v, str) and v.strip(): return v
            if isinstance(v, dict):
                inner = get_localized_name(v, user_lang)
                if inner != "No Name": return inner
    return name if isinstance(name, str) else "No Name"


async def send_admin_preview_media_group(bot, chat_id: int, file_id: str, thumbnail_id: str, caption: str = None):
    media = []
    if thumbnail_id: media.append(InputMediaPhoto(media=thumbnail_id, caption=caption, parse_mode="HTML"))
    if not media:
        return await bot.send_video(chat_id=chat_id, video=file_id, caption=caption, parse_mode="HTML")
    media.append(InputMediaVideo(media=file_id))
    return await bot.send_media_group(chat_id=chat_id, media=media)


def format_multi_caption(caption_data, selected_lang: str = None) -> str:
    return _format_multi_json(caption_data, selected_lang)


def format_multi_name(name_data, selected_lang: str = None) -> str:
    return _format_multi_json(name_data, selected_lang)


def _format_multi_json(json_data, selected_lang: str = None) -> str:
    from src.app.bot.common.languages import LANGUAGES
    data = deep_flatten_name(json_data)
    if not data:
        from src.app.bot.common.i18n import lazy_gettext as _
        return _("Нет")
    if isinstance(data, str): return data
    if isinstance(data, dict):
        if selected_lang:
            short_code = get_lang_code(selected_lang)
            if short_code in data and data[short_code]:
                flag = next((l["flag"] for l in LANGUAGES if l["id"] == short_code), "🌐")
                return f"{flag} {data[short_code]}"
        res = []
        for lang, val in sorted(data.items()):
            if not val: continue
            flag = next((l["flag"] for l in LANGUAGES if l["id"] == get_lang_code(lang)), "🌐")
            res.append(f"{flag} {val}")
        return " | ".join(res) if res else str(data)
    return str(data)
