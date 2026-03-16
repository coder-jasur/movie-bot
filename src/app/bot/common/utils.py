from aiogram.types import User, BufferedInputFile, FSInputFile
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timedelta
logger = logging.getLogger(__name__)


async def get_thumbnail_input(bot, file_id: str):
    """
    Given a Telegram file_id for a photo/thumbnail, return an InputFile
    that aiogram v3 (Pydantic v2) accepts as the `thumbnail` argument.
    
    Uses FSInputFile by downloading to a temporary file first as requested.
    Returns None on any failure so callers can skip the thumbnail gracefully.
    """
    if not file_id:
        logger.debug("get_thumbnail_input: no file_id, skipping")
        return None
    try:
        import os
        import tempfile
        import asyncio
        
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
            abs_path1 = os.path.join(local_base, token, file_path.lstrip('/'))
            if os.path.isfile(abs_path1):
                source_path = abs_path1
            else:
                abs_path2 = os.path.join(local_base, file_path.lstrip('/'))
                if os.path.isfile(abs_path2):
                    source_path = abs_path2

        # 2. Download if not local. Use shared volume for temp files so local API can see them.
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
            # Overlay watermark at top right, and scale output to fit 320x320 for Telegram restrictions
            # Using force_original_aspect_ratio to ensure max(w,h) <= 320
            cmd = [
                "ffmpeg", "-y",
                "-i", source_path,
                "-i", watermark_path,
                "-filter_complex", (
                    f"[1:v]scale=iw/4:-1[wm];"  # scale watermark relative to thumb? No, fixed scale is safer
                    f"[0:v][wm]overlay=W-w-10:10[base];"
                    f"[base]scale=320:320:force_original_aspect_ratio=decrease"
                ),
                output_path
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode == 0:
                    logger.info(f"get_thumbnail_input: applied watermark to {output_path}")
                    return FSInputFile(output_path, filename="thumbnail.jpg")
                else:
                    logger.warning(f"get_thumbnail_input: ffmpeg watermark failed with code {proc.returncode}, stderr: {stderr.decode().strip()}, using raw image")
            except Exception as ffmpeg_e:
                logger.warning(f"get_thumbnail_input: ffmpeg execution failed: {ffmpeg_e}, using raw image")
        
        return FSInputFile(source_path, filename="thumbnail.jpg")

    except Exception as e:
        logger.warning(f"get_thumbnail_input failed for {file_id[:20] if file_id else 'None'}: {e}")
        return None


def get_tashkent_time():
    """Returns current time in Tashkent (UTC+5)."""
    return datetime.utcnow() + timedelta(hours=5)

async def get_user_language(user: User, session: AsyncSession = None) -> str:
    """Get user's bot language preference from DB, falling back to Telegram language."""
    if session:
        from src.app.database.queries.user import UserActions
        db_user = await UserActions(session).get_user(user.id)
        if db_user and db_user.language_code:
            code = db_user.language_code
            if code.startswith("uz"): return "uz"
            if code.startswith("ru"): return "ru"
            if code.startswith("en"): return "en"
            return code
    # Fallback to Telegram language code
    lang = user.language_code
    if not lang: return "uz"
    if lang.startswith("uz"): return "uz"
    if lang.startswith("ru"): return "ru"
    if lang.startswith("en"): return "en"
    return "uz" # Default to uz as per system preference

def deep_parse_json(data):
    """Recursively parse JSON strings within dictionaries and lists."""
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
    """Recursively flatten a nested name/caption dict, unwrapping all encoded JSON layers.
    Handles triply-encoded data like {"uz": "{\"uz\": \"test\"}"} → {"uz": "test"}
    """
    if depth > 15:
        return obj
        
    if isinstance(obj, str):
        stripped = obj.strip()
        if (stripped.startswith('{') and stripped.endswith('}')) or (stripped.startswith('[') and stripped.endswith(']')):
            try:
                # First try regular json
                parsed = json.loads(obj)
                if parsed != obj: # Prevent infinite loop if loads returns same string
                    return deep_flatten_name(parsed, depth + 1)
            except:
                pass
            try:
                # Try literal_eval for single quotes or other Python-item formats
                import ast
                parsed = ast.literal_eval(obj)
                if parsed != obj:
                    return deep_flatten_name(parsed, depth + 1)
            except:
                pass
        return obj  # plain string
        
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            # Standardize key (uz, ru, en)
            from src.app.bot.common.utils import get_lang_code
            nk = get_lang_code(k)
            
            flat_v = deep_flatten_name(v, depth + 1)
            if isinstance(flat_v, dict):
                # Merge inner dict keys (e.g. {"ru": {"ru": "text"}} → {"ru": "text"})
                for ik, iv in flat_v.items():
                    ik_norm = get_lang_code(ik)
                    # If the inner key matches the outer key or result doesn't have it, set it
                    if ik_norm == nk or ik_norm not in result:
                        result[ik_norm] = deep_flatten_name(iv, depth + 1)
            else:
                if nk not in result or not result[nk]:
                    result[nk] = flat_v
        return result
        
    if isinstance(obj, list) and obj:
        # If it's a list, it might be a list of dicts or strings, we usually care about the first meaningful one
        return deep_flatten_name(obj[0], depth + 1)
        
    return obj

def get_lang_code(label: str) -> str:
    """Normalize localized labels or codes to standard 'uz', 'ru', 'en'."""
    if not label: return "uz"
    l = str(label).lower()
    if "o'zbek" in l or "uz" in l: return "uz"
    if "rus" in l or "ru" in l: return "ru"
    if "ingliz" in l or "en" in l or "english" in l: return "en"
    return l

def build_movie_caption(movie, lang: str) -> str:
    """Build a default localized caption for a movie if one is missing in the DB."""
    from src.app.bot.common.genres import get_genre_display_text, deserialize_genres
    from src.app.bot.common.i18n import i18n
    
    lang = get_lang_code(lang)
    _l = lambda x: i18n.gettext(x, locale=lang)
    
    # Identify type icon
    icon = "🎬"
    class_name = movie.__class__.__name__.lower()
    if "series" in class_name:
        icon = "📺"
    if "mini" in class_name:
        icon = "🧩"
        
    genres = getattr(movie, 'genres', "[]")
    genres_text = get_genre_display_text(deserialize_genres(genres), lang=lang)
    code = getattr(movie, 'code', '????')
    raw_name = deep_flatten_name(getattr(movie, 'name', 'No Name'))
    if isinstance(raw_name, dict):
        name = raw_name.get(lang)
        if not name:
            for fl in ["uz", "ru", "en"]:
                if raw_name.get(fl):
                    name = raw_name[fl]
                    break
        if not name and raw_name:
            name = next((v for v in raw_name.values() if isinstance(v, str)), 'No Name')
        if not isinstance(name, str):
            name = str(name)
    else:
        name = str(raw_name) if raw_name else 'No Name'
    
    # Handle episode numbers if applicable
    ep_info = ""
    if hasattr(movie, 'series'):
        if hasattr(movie, 'season'):
            ep_info = f"\n└ 📅 {_l('Mavsum')}: <b>{movie.season}</b>, {_l('Qism')}: <b>{movie.series}</b>"
        else:
            ep_info = f"\n└ 🔢 {_l('Qism')}: <b>{movie.series}</b>"
            
    return (f"{icon} <b>{name}</b>\n"
            f"└ 🎭 {_l('Janr')}: <b>{genres_text}</b>\n"
            f"└ 🆔 {_l('Kod')}: <code>{code}</code>"
            f"{ep_info}")

def resolve_movie_media(movie, user_lang: str, pref_quality: str = None, is_vip: bool = False):
    # 1. Deeply parse JSON structures
    raw_files = deep_parse_json(movie.files)
    raw_captions = deep_parse_json(movie.captions)

    # Normalize: if files is a bare string (legacy file_id), wrap it
    if isinstance(raw_files, str):
        lang_key = getattr(movie, 'language', None) or 'uz'
        lang_key = get_lang_code(lang_key.split(',')[0].strip() or 'uz')
        raw_files = {lang_key: {"original": raw_files}}
    
    # Ensure raw_files is a dict
    if not isinstance(raw_files, dict): raw_files = {}

    # 2. Fully normalize the files dictionary
    # We want: {"uz": {"720p": "id1", ...}, "ru": {...}}
    normalized_files = {}
    qualities_keywords = ["720p", "480p", "1080p", "360p", "240p", "144p", "original"]
    
    # Check if the whole dictionary is flat (qualities at top level)
    is_flat = all(str(k).lower().endswith('p') or str(k).lower() in qualities_keywords for k in raw_files.keys())
    if is_flat and raw_files:
        lang_key = get_lang_code(getattr(movie, 'language', None) or 'uz')
        raw_files = {lang_key: raw_files}

    for lang_key, content in raw_files.items():
        # Normalize language key
        short_code = get_lang_code(lang_key)
        
        # Normalize content to a dict of qualities
        if isinstance(content, str):
            content = {"original": content}
        elif not isinstance(content, dict):
            content = {"original": str(content)}
            
        # Merge if short_code already exists
        if short_code in normalized_files:
            existing = normalized_files[short_code]
            if isinstance(existing, dict) and isinstance(content, dict):
                existing.update(content)
            else:
                # If one is a string (legacy) and other is dict, prefer dict
                normalized_files[short_code] = content if isinstance(content, dict) else existing
        else:
            normalized_files[short_code] = content

    files = normalized_files
    
    # 3. Handle Captions similarly
    if isinstance(raw_captions, str):
        lang_key = get_lang_code(getattr(movie, 'language', None) or 'uz')
        raw_captions = {lang_key: raw_captions}
    
    captions = {}
    if isinstance(raw_captions, dict):
        for k, v in raw_captions.items():
            # Unwrap nested dicts from old bug: {"en": {"en": "text"}} → {"en": "text"}
            if isinstance(v, dict):
                # Extract string value from nested dict
                flat = next((val for val in v.values() if isinstance(val, str)), str(v))
                captions[get_lang_code(k)] = flat
            else:
                captions[get_lang_code(k)] = v

    # 4. Select Target Language
    # Use normalized short code for selection
    user_lang = get_lang_code(user_lang)
    target_lang = user_lang if user_lang in files else None
    
    # Fallback in order
    if not target_lang:
        for l in ["uz", "ru", "en"]:
            if l in files:
                target_lang = l
                break
                
    if not target_lang and files:
        target_lang = list(files.keys())[0]
        
    if not target_lang:
        # Final fallback to base video_file_id
        return getattr(movie, 'video_file_id', None), getattr(movie, 'name', "No Name"), getattr(movie, 'captions', "No caption"), "uz", "original", {}, {}, None

    lang_files = files.get(target_lang, {})
    
    # 5. Select Quality
    target_quality = "original"
    if lang_files:
        # Preferred quality (provided when user selects from menu)
        if pref_quality and pref_quality in lang_files:
            target_quality = pref_quality
        else:
            # Default quality selection based on VIP status (when entering code)
            def get_quality_rank(q: str) -> int:
                q_clean = str(q).lower().strip()
                if q_clean == "original": return 9999
                if q_clean.endswith("p"):
                    with suppress(Exception):
                        return int(q_clean[:-1])
                return 0

            from contextlib import suppress
            
            # Get all available qualities with their ranks
            available_ranks = []
            for q_key in lang_files.keys():
                available_ranks.append((q_key, get_quality_rank(q_key)))
            
            # Sort by rank descending
            available_ranks.sort(key=lambda x: x[1], reverse=True)

            if is_vip:
                # VIP: Highest quality available.
                # If 'original' is top, and there are ANY named qualities, prefer the highest named one
                # to provide a better label (e.g. '1080p' instead of 'Original').
                if available_ranks:
                    best_q, best_rank = available_ranks[0]
                    if best_q == "original" and len(available_ranks) > 1:
                        # Pick the second best (which is the highest numeric one)
                        next_q, next_rank = available_ranks[1]
                        target_quality = next_q
                    else:
                        target_quality = best_q
            else:
                # Not VIP: Highest quality <= 480p
                non_vip_options = [x for x in available_ranks if x[1] <= 480]
                if non_vip_options:
                    # If we have named qualities <= 480p, pick the best named one.
                    # Note: if 'original' was 480p, its rank 9999 would exclude it from non_vip_options.
                    # We should handle the case where 'original' is the ONLY quality or it is <= 480p.
                    target_quality = non_vip_options[0][0]
                else:
                    # Fallback if only high qualities or ONLY 'original' exists
                    if available_ranks:
                        # If 'original' is the only one, or all named ones are > 480p
                        # we pick the lowest available named one OR 'original' if it's the only one.
                        target_quality = available_ranks[-1][0] 
                    
        file_id = lang_files.get(target_quality, lang_files.get("original", getattr(movie, 'video_file_id', None)))
    else:
        file_id = getattr(movie, 'video_file_id', None)

    # 6. Resolve Caption & Name
    final_name = get_localized_name(movie, user_lang)
    
    # User selected language (uz, ru, en)
    final_caption = captions.get(user_lang)

    # 1. Fallback: If no caption for selected language, try the file's primary language
    if not final_caption:
        final_caption = captions.get(target_lang)
        if final_caption:
            logger.info(f"Using Fallback Caption (target_lang): {target_lang}")
        
    # 2. Fallback: Any available string caption in the dictionary
    if not final_caption and captions:
        for v in captions.values():
            if isinstance(v, str) and v.strip():
                final_caption = v
                logger.info(f"Using First Available Caption Fallback")
                break
                
    # 3. Fallback: If absolutely no caption exists, use the dynamic header
    if not final_caption:
        final_caption = build_movie_caption(movie, user_lang)
        logger.info("Using Dynamic Header Fallback")
            
    # Final type safety for Telegram
    if not isinstance(final_caption, str):
        final_caption = str(final_caption) if final_caption else "No caption"
    
    logger.info(f"Final Resolved Caption Length: {len(final_caption)}")
    
    # 7. Resolve Thumbnail
    raw_thumbnails = deep_parse_json(getattr(movie, 'thumbnails', {}))
    if not isinstance(raw_thumbnails, dict):
        # Handle legacy string if any
        if isinstance(raw_thumbnails, str) and raw_thumbnails.strip():
            raw_thumbnails = {"uz": raw_thumbnails}
        else:
            raw_thumbnails = {}
    
    final_thumbnails = {get_lang_code(k): v for k, v in raw_thumbnails.items() if isinstance(v, str)}
    
    # Selection logic for thumbnail (similar to video/caption)
    thumbnail_id = final_thumbnails.get(user_lang)
    if not thumbnail_id:
        thumbnail_id = final_thumbnails.get(target_lang)
    if not thumbnail_id:
        for l in ["uz", "ru", "en"]:
            if l in final_thumbnails:
                thumbnail_id = final_thumbnails[l]
                break
    if not thumbnail_id and final_thumbnails:
        thumbnail_id = next(iter(final_thumbnails.values()))

    return file_id, final_name, final_caption, target_lang, target_quality, files, captions, thumbnail_id

def get_localized_name(movie, user_lang: str) -> str:
    """Resolve a localized name for a movie object or dictionary based on user language.
    Logic: 1. User Language | 2. Default (Uzbek) | 3. First Available
    """
    # Handle both movie objects and dictionaries
    if hasattr(movie, 'name'):
        data = movie.name
    elif isinstance(movie, dict) and 'name' in movie:
        data = movie['name']
    else:
        data = movie
        
    # deep_flatten_name handles all layers of nested encoding
    raw_names = deep_flatten_name(data)
    
    if isinstance(raw_names, str):
        return raw_names
        
    if not isinstance(raw_names, dict):
        return str(raw_names) if raw_names else "No Name"
        
    # Standardize user language code
    user_lang = get_lang_code(user_lang)
        
    # 1. Try requested language
    name = raw_names.get(user_lang)
    if name and isinstance(name, str):
        return name
        
    # 2. Try default (Uzbek) fallback
    if user_lang != "uz":
        val = raw_names.get("uz")
        if val and isinstance(val, str):
            return val
            
    # 3. Final fallback: First string value found in the dict
    for v in raw_names.values():
        if isinstance(v, str) and v.strip():
            return v
        if isinstance(v, dict):
            # If still a dict, recurse one step for that value
            inner = get_localized_name(v, user_lang)
            if inner and inner != "No Name":
                return inner
        
    return "No Name"
    
async def send_admin_preview_media_group(bot, chat_id: int, file_id: str, thumbnail_id: str, caption: str = None):
    """Sends a Media Group (Poster + Video) for admin preview purposes."""
    from aiogram.types import InputMediaPhoto, InputMediaVideo
    media = []
    if thumbnail_id:
        media.append(InputMediaPhoto(media=thumbnail_id, caption=caption, parse_mode="HTML"))
    
    # If no thumbnail, we just send a single video with caption
    if not media:
        await bot.send_video(chat_id=chat_id, video=file_id, caption=caption, parse_mode="HTML")
        return
        
    media.append(InputMediaVideo(media=file_id))
    
    # Note: Telegram allows only the first item in MediaGroup to have a caption if it's sent as an album.
    return await bot.send_media_group(chat_id=chat_id, media=media)

def format_multi_caption(caption_data, selected_lang: str = None) -> str:
    """Format a dictionary of captions into a readable string for admin summaries."""
    return _format_multi_json(caption_data, selected_lang)

def format_multi_name(name_data, selected_lang: str = None) -> str:
    """Format a dictionary of localized names into a readable string for admin summaries."""
    return _format_multi_json(name_data, selected_lang)

def _format_multi_json(json_data, selected_lang: str = None) -> str:
    from src.app.bot.common.languages import LANGUAGES
    
    data = deep_flatten_name(json_data)
            
    if not data:
        from src.app.bot.common.i18n import lazy_gettext as _
        return _("Нет")
    
    if isinstance(data, str):
        return data
        
    if isinstance(data, dict):
        if selected_lang:
            short_code = get_lang_code(selected_lang)
            if short_code in data:
                val = data[short_code]
                if val:
                    flag = "🌐"
                    for l_info in LANGUAGES:
                        if l_info["id"] == short_code:
                            flag = l_info.get("flag", "🌐")
                            break
                    return f"{flag} {val}"
        
        res = []
        for lang in sorted(data.keys()):
            val = data[lang]
            if not val: continue
            # Ensure val is a plain string at this point
            if not isinstance(val, str):
                val = str(val)

            # Find label and flag
            flag = "🌐"
            short_code = get_lang_code(lang)
            for l_info in LANGUAGES:
                if l_info["id"] == short_code:
                    flag = l_info.get("flag", "🌐")
                    break
            
            res.append(f"{flag} {val}")
        return " | ".join(res) if res else str(data)
        
    return str(data)
