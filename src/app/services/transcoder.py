import asyncio
import logging
import os
import shutil
import tempfile
from asyncio import subprocess
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

from aiogram import Bot
from aiohttp import ClientTimeout

from src.app.bot.common.i18n import i18n

logger = logging.getLogger(__name__)

TARGET_QUALITIES = {
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
}

MAX_PARALLEL_WORKERS = 1

BASE_DIR = "/app"
INTRO_MKV = os.path.join(BASE_DIR, "media/videos/intro.mkv")
INTRO_MP4 = os.path.join(BASE_DIR, "media/videos/intro.mp4")
INTRO_PATH = INTRO_MKV if os.path.exists(INTRO_MKV) else INTRO_MP4
WATERMARK_PATH = os.path.join(BASE_DIR, "media/photos/bot_watermark.png")
TMP_BASE = "/var/lib/telegram-bot-api/temp"

# ✅ Videoga Intro va Watermark qo'shishni boshqarish
# True bo'lsa qo'shadi, False bo'lsa yo'q.
ADD_INTRO_AND_WATERMARK_TO_VIDEO = True

LOCAL_API_BASE = "/var/lib/telegram-bot-api"

# ✅ Local API server URL (container name orqali)
TELEGRAM_BOT_API_URL = os.environ.get(
    "TELEGRAM_BOT_API_URL", "http://telegram-bot-api:8081"
)

StatusCallback = Optional[Callable[[str], Awaitable[None]]]
QualityCallback = Optional[Callable[[str, str], Awaitable[None]]]


def _t(key: str, locale: str, **kwargs) -> str:
    text = i18n.gettext(key, locale=locale)
    return text.format(**kwargs) if kwargs else text


_NVENC_CACHE: Optional[bool] = None


async def _check_nvenc() -> bool:
    global _NVENC_CACHE
    if _NVENC_CACHE is not None:
        return _NVENC_CACHE
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-encoders",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        _NVENC_CACHE = "h264_nvenc" in out.decode()
    except Exception:
        _NVENC_CACHE = False
    logger.info(f"Encoder: {'h264_nvenc (GPU)' if _NVENC_CACHE else 'libx264 (CPU)'}")
    return _NVENC_CACHE


def _enc(nvenc: bool, h: int) -> list:
    # ✅ Hajmni optimallashtirish uchun CRF qiymatlari (balandroq = kichikroq hajm)
    if h >= 900:
        crf, maxrate, bufsize = "28", "4M", "8M"
    elif h >= 550:
        crf, maxrate, bufsize = "26", "2M", "4M"
    elif h >= 400:
        crf, maxrate, bufsize = "26", "1M", "2M"
    else:
        crf, maxrate, bufsize = "40", "500k", "1M"

    if nvenc:
        return [
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p2",
            "-cq",
            crf,
            "-maxrate:v",
            maxrate,
            "-bufsize:v",
            bufsize,
            "-c:a",
            "aac",
            "-b:a",
            "128k",
        ]
    return [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        crf,
        "-maxrate:v",
        maxrate,
        "-bufsize:v",
        bufsize,
        "-c:a",
        "aac",
        "-b:a",
        "128k",
    ]


async def _make_thumb_with_watermark(thumb_in: str, thumb_out: str) -> bool:
    if not os.path.isfile(WATERMARK_PATH):
        try:
            # ✅ Watermark yo'q — rasmni 320x320 ga crop bilan to'ldiramiz (qora chegara yo'q)
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                thumb_in,
                "-vf",
                "scale=320:320:force_original_aspect_ratio=increase,crop=320:320,setsar=1",
                "-q:v",
                "2",
                thumb_out,
            ]
            proc = await asyncio.create_subprocess_exec(*cmd, stderr=subprocess.PIPE)
            await proc.communicate()
            return True
        except Exception:
            shutil.copy2(thumb_in, thumb_out)
            return True
    try:
        # ✅ 320x320 crop bilan to'ldirish + watermark tepada (top-right) + shafoflik YO'Q
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            thumb_in,
            "-i",
            WATERMARK_PATH,
            "-filter_complex",
            "[0:v]scale=320:320:force_original_aspect_ratio=increase,crop=320:320,setsar=1[bg];"
            "[1:v]scale=iw*0.20:-2[wm];"
            "[bg][wm]overlay=W-w-10:10",
            "-frames:v",
            "1",
            "-q:v",
            "2",
            thumb_out,
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stderr=subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error(f"Thumb watermark xato: {stderr.decode()[-200:]}")
            shutil.copy2(thumb_in, thumb_out)
            return False
        return True
    except Exception as e:
        logger.error(f"Thumb watermark exception: {e}")
        shutil.copy2(thumb_in, thumb_out)
        return False


def _resolve_local_path(token: str, file_path: str) -> Optional[str]:
    """
    Telegram Local API file_path ni haqiqiy fayl yo'liga aylantiradi.
    """
    bot_id = token.split(":")[0] if ":" in token else token

    candidates = [
        file_path,
        os.path.join(LOCAL_API_BASE, token, file_path.lstrip("/")),
        os.path.join(LOCAL_API_BASE, bot_id, file_path.lstrip("/")),
        os.path.join(LOCAL_API_BASE, file_path.lstrip("/")),
    ]

    for path in candidates:
        if os.path.isfile(path):
            logger.info(f"Local file found: {path}")
            return path

    logger.debug(
        f"Local file not found for file_path={file_path!r}, tried: {candidates}"
    )
    return None


def _make_relative_path(token: str, file_path: str) -> str:
    """
    Local API HTTP download uchun nisbiy yo'l qaytaradi.
    """
    bot_id = token.split(":")[0] if ":" in token else token

    for prefix in [
        f"{LOCAL_API_BASE}/{token}/",
        f"{LOCAL_API_BASE}/{bot_id}/",
        f"{LOCAL_API_BASE}/",
    ]:
        if file_path.startswith(prefix):
            return file_path[len(prefix) :]

    return file_path.lstrip("/")


async def _verify_video_file(path: str) -> None:
    """
    FFprobe orqali fayl yaxlitligini tekshiradi.
    Buzilgan yoki bo'sh faylda Exception ko'taradi.
    """
    if not os.path.exists(path):
        raise Exception(f"Video file does not exist: {path}")

    size = os.path.getsize(path)
    if size < 1024:
        raise Exception(f"Video file too small ({size} bytes): {path}")

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_type",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = await proc.communicate()
    output = out.decode().strip().lower()
    if proc.returncode != 0 or "video" not in output:
        raise Exception(
            f"Video file verification failed (returncode={proc.returncode}): "
            f"{err.decode()[-300:]}"
        )
    logger.info(f"File verified OK: {path} ({size / 1024 / 1024:.2f} MB)")


class Transcoder:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def process_video(
        self,
        file_id: str,
        user_id: int,
        status_callback: StatusCallback,
        on_quality_ready: Optional[QualityCallback] = None,
        thumbnail_file_id: Optional[str] = None,
        locale: str = "uz",
        manual_quality: Optional[str] = None,
    ) -> Tuple[Dict[str, str], List[str]]:
        local_to_cleanup = []
        os.makedirs(TMP_BASE, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TMP_BASE, prefix="tc_") as tmp:
            source = os.path.join(tmp, "source.mp4")
            try:
                file_info = await self.bot.get_file(file_id)
            except Exception as e:
                logger.error(f"get_file failed: {e}")
                return {"original": file_id}, []

            await self._notify(status_callback, _t("📥 Video yuklanmoqda...", locale))

            try:
                local_src = await self._download(file_id, file_info.file_path, source)
                if local_src:
                    local_to_cleanup.append(local_src)
            except Exception as e:
                logger.error(f"Download failed: {e}")
                return {"original": file_id}, []

            thumb_wm_path: Optional[str] = None
            if thumbnail_file_id:
                thumb_raw = await self._prepare_thumbnail(thumbnail_file_id, tmp)
                if thumb_raw:
                    thumb_wm = os.path.join(tmp, "thumb_wm.jpg")
                    await _make_thumb_with_watermark(thumb_raw, thumb_wm)
                    thumb_wm_path = thumb_wm if os.path.exists(thumb_wm) else thumb_raw

            def get_standard_label(h: int) -> str:
                if h >= 900:
                    return "1080p"
                if h >= 550:
                    return "720p"
                if h >= 400:
                    return "480p"
                return "360p"

            if manual_quality:
                q_name = manual_quality
                orig_h = await self._get_height(source) or TARGET_QUALITIES.get(
                    q_name, 720
                )
            else:
                orig_h = await self._get_height(source)
                if not orig_h:
                    logger.warning("Could not detect video height, skipping scaling.")
                    return {"original": file_id}, local_to_cleanup
                q_name = get_standard_label(orig_h)

            logger.info(f"Target quality: {q_name} (Source Height: {orig_h})")
            q_h_val = TARGET_QUALITIES.get(q_name, 720)

            a_main = await self._has_audio(source)
            a_intro = (
                await self._has_audio(INTRO_PATH)
                if os.path.isfile(INTRO_PATH)
                else False
            )

            # 🎬 Base video tayyorlash (faqat intro yoki watermark qo'shish yoqilgan bo'lsa)
            has_intro = (
                (os.path.isfile(INTRO_PATH) if INTRO_PATH else False)
                if ADD_INTRO_AND_WATERMARK_TO_VIDEO
                else False
            )
            has_wm = (
                (os.path.isfile(WATERMARK_PATH) if WATERMARK_PATH else False)
                if ADD_INTRO_AND_WATERMARK_TO_VIDEO
                else False
            )

            if has_intro or has_wm:
                await self._notify(
                    status_callback, _t("🎬 Base video tayyorlanmoqda...", locale)
                )
                base_path = os.path.join(tmp, "base.mp4")
                try:
                    await self._make_base(source, base_path, orig_h, a_main, a_intro)
                except Exception as e:
                    logger.error(f"Base video xato: {e}", exc_info=True)
                    base_path = source
            else:
                base_path = source

            results: Dict[str, str] = {}
            file_sizes: Dict[str, float] = {}

            q_name = get_standard_label(orig_h)
            await self._notify(
                status_callback, _t("💾 Original tayyorlanmoqda...", locale)
            )
            try:
                out_orig = os.path.join(tmp, "orig.mp4")
                # Original faylning razmerini o'zgartirmaymiz (Option A), lekin uning
                # q_name ga mos CRF qo'llaniladi (chunki _enc da h>=550 tekshiruvi bor).
                await self._scale_only(base_path, out_orig, orig_h)

                self._fsync_file(out_orig)
                self._ensure_permissions(out_orig)
                await _verify_video_file(out_orig)

                if os.path.exists(out_orig):
                    file_sizes[q_name] = os.path.getsize(out_orig) / (1024 * 1024)

                res = await self._upload(out_orig, user_id, q_name, thumb_wm_path)
                results[q_name] = res if res else file_id

                if res and on_quality_ready:
                    await on_quality_ready(q_name, res)
            except Exception as e:
                logger.error(f"Original upload failed: {e}")
                results[q_name] = file_id
            finally:
                p = os.path.join(tmp, "orig.mp4")
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

            to_do = [(name, h) for name, h in TARGET_QUALITIES.items() if h < q_h_val]
            logger.info(f"Qualities to process: {to_do}")

            if to_do:
                await self._notify(
                    status_callback,
                    _t("⚙️ {n} ta sifat tayyorlanmoqda...", locale, n=len(to_do)),
                )
                sem = asyncio.Semaphore(MAX_PARALLEL_WORKERS)
                tasks = [
                    self._scale_and_upload(
                        base_path,
                        tmp,
                        h,
                        name,
                        user_id,
                        i,
                        len(to_do),
                        sem,
                        status_callback,
                        on_quality_ready,
                        thumb_wm_path,
                        locale,
                        file_sizes,
                    )
                    for i, (name, h) in enumerate(to_do, 1)
                ]
                for name, res in zip(
                    [t[0] for t in to_do], await asyncio.gather(*tasks)
                ):
                    if res:
                        results[name] = res

            if base_path != source and os.path.exists(base_path):
                try:
                    os.remove(base_path)
                except Exception:
                    pass

            await self._notify(
                status_callback,
                _t("✅ Tayyor! {n} ta format.", locale, n=len(results)),
            )
            logger.info(f"process_video done: {list(results.keys())}")

            size_summary = ", ".join([f"{q}: {s:.2f}MB" for q, s in file_sizes.items()])
            logger.info(f"Transcoding complete. Sizes: {size_summary}")
            if status_callback:
                await self._notify(
                    status_callback,
                    _t("✅ Tayyor! Hajmlar: {s}", locale, s=size_summary),
                )

            return results, local_to_cleanup

    async def _prepare_thumbnail(self, file_id: str, tmp_dir: str) -> Optional[str]:
        path = os.path.join(tmp_dir, "thumb.jpg")
        try:
            file_info = await self.bot.get_file(file_id)
            await self._download(file_id, file_info.file_path, path)
            return path
        except Exception as e:
            logger.error(f"Thumb prepare failed: {e}")
            return None

    async def _make_base(
        self, source: str, dest: str, h: int, a_main: bool, a_intro: bool
    ):
        has_intro = (
            (os.path.isfile(INTRO_PATH) if INTRO_PATH else False)
            if ADD_INTRO_AND_WATERMARK_TO_VIDEO
            else False
        )
        has_wm = (
            (os.path.isfile(WATERMARK_PATH) if WATERMARK_PATH else False)
            if ADD_INTRO_AND_WATERMARK_TO_VIDEO
            else False
        )
        nvenc = await _check_nvenc()

        w_raw = await self._get_width(source)
        h_raw = await self._get_height(source)
        if w_raw and h_raw:
            w = int(w_raw * h / h_raw)
            w = w if w % 2 == 0 else w + 1
        else:
            w = int(h * 16 / 9)
            w = w if w % 2 == 0 else w + 1

        cmd = ["ffmpeg", "-y"]
        if nvenc:
            cmd.extend(["-hwaccel", "cuda"])
        cmd.extend(["-i", source])
        if has_intro:
            cmd.extend(["-i", INTRO_PATH])
        wm_idx = 2 if has_intro else 1
        if has_wm:
            cmd.extend(["-i", WATERMARK_PATH])

        fp = []
        ma = []

        norm_main = (
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[main_v]"
        )
        norm_intro = (
            f"[1:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[intro_v]"
        )

        if has_intro and has_wm:
            fp.append(norm_intro)
            fp.append(norm_main)
            fp.append(
                f"[{wm_idx}:v]format=rgba,colorchannelmixer=aa=0.5,scale={w}*0.15:-2[wm_s];[wm_s]split[wm1][wm2]"
            )
            fp.append("[intro_v][wm1]overlay=W-w-15:H-h-30[intro_wm]")
            fp.append("[main_v][wm2]overlay=W-w-15:H-h-30[main_wm]")
            if a_intro and a_main:
                fp.append("[intro_wm][1:a][main_wm][0:a]concat=n=2:v=1:a=1[v][a]")
                ma = ["-map", "[v]", "-map", "[a]"]
            elif a_main:
                fp.append("aevalsrc=0:c=stereo:s=44100:d=1[intro_sil]")
                fp.append("[intro_wm][intro_sil][main_wm][0:a]concat=n=2:v=1:a=1[v][a]")
                ma = ["-map", "[v]", "-map", "[a]"]
            else:
                fp.append("[intro_wm][main_wm]concat=n=2:v=1:a=0[v]")
                ma = ["-map", "[v]"]

        elif has_intro and not has_wm:
            fp.append(norm_intro)
            fp.append(norm_main)
            if a_intro and a_main:
                fp.append("[intro_v][1:a][main_v][0:a]concat=n=2:v=1:a=1[v][a]")
                ma = ["-map", "[v]", "-map", "[a]"]
            elif a_main:
                fp.append("aevalsrc=0:c=stereo:s=44100:d=1[intro_sil]")
                fp.append("[intro_v][intro_sil][main_v][0:a]concat=n=2:v=1:a=1[v][a]")
                ma = ["-map", "[v]", "-map", "[a]"]
            else:
                fp.append("[intro_v][main_v]concat=n=2:v=1:a=0[v]")
                ma = ["-map", "[v]"]

        elif not has_intro and has_wm:
            fp.append(norm_main)
            fp.append(
                f"[{wm_idx}:v]format=rgba,colorchannelmixer=aa=0.5,scale={w}*0.22:-2[wm]"
            )
            fp.append("[main_v][wm]overlay=W-w-15:H-h-30[v]")
            ma = ["-map", "[v]", "-map", "0:a?"]

        else:
            cmd.extend(["-c", "copy", dest])
            proc = await asyncio.create_subprocess_exec(*cmd, stderr=subprocess.PIPE)
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise Exception(f"FFmpeg copy error: {stderr.decode()[-500:]}")
            return

        cmd.extend(["-filter_complex", ";".join(fp)])
        cmd.extend(ma)
        cmd.extend(["-movflags", "+faststart"])
        cmd.extend(_enc(nvenc, h))
        cmd.append(dest)

        proc = await asyncio.create_subprocess_exec(*cmd, stderr=subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise Exception(f"FFmpeg base error: {stderr.decode()[-500:]}")

    async def _scale_only(self, base: str, dest: str, h: int):
        w_orig = await self._get_width(base)
        h_orig = await self._get_height(base)
        nvenc = await _check_nvenc()

        if w_orig and h_orig and h_orig > 0:
            w = int(w_orig * h / h_orig)
            w = w if w % 2 == 0 else w + 1
        else:
            w = -2

        w_str = str(w) if w > 0 else "-2"
        cmd = ["ffmpeg", "-y"]
        if nvenc:
            cmd.extend(["-hwaccel", "cuda"])
        cmd.extend(["-i", base])
        cmd.extend(
            ["-vf", f"scale={w_str}:{h},format=yuv420p", "-map", "0:v", "-map", "0:a?"]
        )
        cmd.extend(["-movflags", "+faststart"])
        cmd.extend(_enc(nvenc, h))
        cmd.append(dest)

        proc = await asyncio.create_subprocess_exec(*cmd, stderr=subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise Exception(f"FFmpeg scale error: {stderr.decode()[-500:]}")

    async def _scale_and_upload(
        self,
        base: str,
        tmp_dir: str,
        height: int,
        name: str,
        user_id: int,
        idx: int,
        total: int,
        sem: asyncio.Semaphore,
        status_callback: StatusCallback,
        on_quality_ready: QualityCallback,
        thumb_wm_path: Optional[str],
        locale: str,
        file_sizes: Dict[str, float],  # ✅ Hajmlarni yig'ish uchun
    ) -> Optional[str]:
        async with sem:
            out = os.path.join(tmp_dir, f"v_{height}p.mp4")
            try:
                await self._notify(
                    status_callback,
                    _t(
                        "🔄 {n} tayyorlanmoqda ({i}/{t})...",
                        locale,
                        n=name,
                        i=idx,
                        t=total,
                    ),
                )
                await self._scale_only(base, out, height)

                # ✅ Havmni o'lchash
                if os.path.exists(out):
                    file_sizes[name] = os.path.getsize(out) / (1024 * 1024)

                # ✅ Fayl diskka to'liq yozilganini ta'minlash
                self._fsync_file(out)
                self._ensure_permissions(out)
                # ✅ Yaxlitlikni tekshirish
                await _verify_video_file(out)
                await self._notify(
                    status_callback,
                    _t(
                        "📤 {n} yuklanmoqda ({i}/{t})...",
                        locale,
                        n=name,
                        i=idx,
                        t=total,
                    ),
                )
                res = await self._upload(out, user_id, name, thumb_wm_path)
                if res and on_quality_ready:
                    await on_quality_ready(name, res)
                return res
            except Exception as e:
                logger.error(f"Scale/Upload {name} failed: {e}")
                return None
            finally:
                if os.path.exists(out):
                    try:
                        os.remove(out)
                    except Exception:
                        pass

    async def _upload(
        self,
        path: str,
        user_id: int,
        label: str,
        thumb_path: Optional[str] = None,
    ) -> Optional[str]:
        from aiogram.client.default import DefaultBotProperties
        from aiogram.client.session.aiohttp import AiohttpSession
        from aiogram.client.telegram import TelegramAPIServer
        from aiogram.methods import SendVideo
        from aiogram.types import FSInputFile
        from aiohttp import TCPConnector

        token = self.bot.token

        # ✅ Yuklashdan oldin fayl mavjudligi va yaxlitligini tekshirish
        if not os.path.exists(path):
            logger.error(f"File not found before upload: {path}")
            return None

        file_size = os.path.getsize(path)
        logger.info(f"Uploading {label}: {path} ({file_size / 1024 / 1024:.2f} MB)")

        if file_size == 0:
            logger.error(f"File is empty: {path}")
            return None

        # ✅ Bot yaratilgan server URL ni olish, container nomi bilan
        try:
            api_server = self.bot.session.api
        except Exception:
            api_server = TelegramAPIServer.from_base(
                TELEGRAM_BOT_API_URL, is_local=True
            )

        max_retries = 5
        for attempt in range(1, max_retries + 1):
            # ✅ Har urinishda yangi sessiya va bot yaratamiz (BaseSession xatosi tuzatildi)
            session = AiohttpSession(
                api=api_server,
                timeout=ClientTimeout(
                    total=3600, connect=60, sock_read=3600, sock_connect=60
                ),
            )
            thumb_tg_path = None
            try:
                async with Bot(
                    token=token,
                    session=session,
                    default=DefaultBotProperties(parse_mode="HTML"),
                ) as upload_bot:
                    tg_thumb = None

                    # ✅ Sifatni saqlash: rasm allaqachon _make_thumb_with_watermark orqali 1280x720 qilingan
                    if thumb_path and os.path.exists(thumb_path):
                        tg_thumb = FSInputFile(thumb_path)

                    # ✅ Yuklashdan oldin fayl hali mavjudligini tekshirish
                    if not os.path.exists(path):
                        raise Exception(
                            f"File disappeared before upload attempt {attempt}: {path}"
                        )

                    send_kwargs = dict(
                        chat_id=user_id,
                        video=FSInputFile(path),
                        caption=f"✅ {label} tayyor.",
                        disable_notification=True,
                        supports_streaming=True,
                    )
                    if tg_thumb:
                        # ✅ 'thumbnail' o'rniga 'cover' ishlatamiz (sifat uchun)
                        send_kwargs["cover"] = tg_thumb

                    msg = await upload_bot(
                        SendVideo(**send_kwargs),
                        request_timeout=7200,
                    )

                    if msg and msg.video:
                        logger.info(f"Upload {label} OK: {msg.video.file_id}")
                        return msg.video.file_id

                    logger.error(f"Upload {label} attempt {attempt}: msg.video is None")
                    return None

            except Exception as e:
                logger.warning(f"Upload {label} attempt {attempt} failed: {e}")
                if attempt == max_retries:
                    logger.error(
                        f"Upload {label} finally failed after {max_retries} attempts."
                    )
                    return None
                # ✅ Ko'proq kutish (backoff x5): 150s, 300s, 450s, 600s, 750s
                await asyncio.sleep(400 * attempt)
            finally:
                if thumb_tg_path and os.path.exists(thumb_tg_path):
                    try:
                        os.remove(thumb_tg_path)
                    except Exception:
                        pass
        return None

    async def _download(self, file_id: str, file_path: str, dest: str) -> Optional[str]:
        token = self.bot.token

        # ── 1. Fayl tizimidan to'g'ridan-to'g'ri topish ──────────────────────
        local_path = _resolve_local_path(token, file_path)
        if local_path:
            await asyncio.to_thread(shutil.copy2, local_path, dest)
            return local_path

        # ── 2. Local API HTTP orqali yuklab olish ─────────────────────────────
        relative = _make_relative_path(token, file_path)
        logger.info(f"Trying Local API HTTP download: relative_path={relative!r}")
        try:
            await self.bot.download_file(relative, dest)
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                logger.info(f"Local API HTTP download OK: {dest}")
                return dest
        except Exception as e:
            logger.warning(f"Local API download failure: {e}")

        # ── 3. Global API — faqat 20MB dan kichik fayllar uchun ──────────────
        logger.warning("Falling back to Global API (20MB limit applies)")
        from aiogram.client.session.aiohttp import AiohttpSession

        async with AiohttpSession() as session:
            temp_bot = Bot(token=token, session=session)
            try:
                fi = await temp_bot.get_file(file_id)
                if fi.file_size and fi.file_size > 20 * 1024 * 1024:
                    raise ValueError(
                        f"File too big for Global API: {fi.file_size} bytes "
                        f"({fi.file_size // 1024 // 1024}MB)"
                    )
                await temp_bot.download_file(fi.file_path, dest)
                logger.info("Global API download OK")
                return dest
            except Exception as e:
                logger.error(f"Global API failure: {e}")
                raise
            finally:
                await temp_bot.session.close()

    async def _get_height(self, path: str) -> int:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=height",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        out, _ = await proc.communicate()
        try:
            return int(out.decode().strip())
        except Exception:
            return 0

    async def _get_width(self, path: str) -> int:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        out, _ = await proc.communicate()
        try:
            return int(out.decode().strip())
        except Exception:
            return 0

    async def _has_audio(self, path: str) -> bool:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        out, _ = await proc.communicate()
        return "audio" in out.decode().lower()

    @staticmethod
    def _fsync_file(path: str):
        """
        Faylni OS buffer'dan diskka to'liq yozilishini ta'minlaydi.
        FILE_PARTS_INVALID xatosining asosiy sababini bartaraf etadi.
        """
        try:
            with open(path, "rb") as f:
                os.fsync(f.fileno())
            logger.debug(f"fsync OK: {path}")
        except Exception as e:
            logger.warning(f"fsync failed for {path}: {e}")

    @staticmethod
    def _ensure_permissions(path: str):
        """Sets 777 permissions for the file and its parent folder for Local API access."""
        try:
            if os.path.exists(path):
                os.chmod(path, 0o777)
                parent = os.path.dirname(path)
                if os.path.exists(parent):
                    os.chmod(parent, 0o777)
        except Exception as e:
            logger.warning(f"Could not set permissions for {path}: {e}")

    @staticmethod
    async def _notify(cb: StatusCallback, text: str):
        if cb:
            try:
                await cb(text)
            except Exception:
                pass
