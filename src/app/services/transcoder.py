import asyncio
import logging
import os
import shutil
import tempfile
from asyncio import subprocess
from typing import Awaitable, Callable, Dict, Optional

from aiogram import Bot
from aiogram.types import BufferedInputFile, FSInputFile

from src.app.bot.common.i18n import lazy_gettext as gt

logger = logging.getLogger(__name__)

TARGET_QUALITIES = {
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
}

MAX_PARALLEL_WORKERS = 2
BASE_DIR = "/app"

INTRO_MKV = os.path.join(BASE_DIR, "media/videos/intro.mkv")
INTRO_MP4 = os.path.join(BASE_DIR, "media/videos/intro.mp4")
INTRO_PATH = INTRO_MKV if os.path.exists(INTRO_MKV) else INTRO_MP4

WATERMARK_PATH = os.path.join(BASE_DIR, "media/photos/bot_watermark.png")

TMP_BASE = "/var/lib/telegram-bot-api/temp"

StatusCallback = Optional[Callable[[str], Awaitable[None]]]


class Transcoder:
    def __init__(self, bot: Bot):
        self.bot = bot

    # ═══════════════════════════════════════════
    # PUBLIC
    # ═══════════════════════════════════════════

    async def process_video(
        self,
        file_id: str,
        user_id: int,
        status_callback: StatusCallback = None,
        thumbnail_file_id: str = None,
    ) -> Dict[str, str]:

        try:
            file_info = await self.bot.get_file(file_id)
        except Exception as e:
            logger.error(f"get_file failed: {e}")
            return {"original": file_id}

        os.makedirs(TMP_BASE, exist_ok=True)

        with tempfile.TemporaryDirectory(dir=TMP_BASE, prefix="tc_") as tmp:
            source = os.path.join(tmp, "source.mp4")

            # 1. Video yuklab olish
            await self._notify(status_callback, str(gt("📥 Video yuklanmoqda...")))
            try:
                await self._download(file_info.file_path, source)
            except Exception as e:
                logger.error(f"Download failed: {e}")
                return {"original": file_id}

            # 2. Thumbnail tayyorlash (watermark qo'shilgan, 320x180 JPEG)
            thumb_path: Optional[str] = None
            if thumbnail_file_id:
                thumb_path = await self._prepare_thumbnail(thumbnail_file_id, tmp)
                if thumb_path:
                    logger.info(
                        f"Thumbnail tayyor: {thumb_path} ({os.path.getsize(thumb_path)} bytes)"
                    )

            # 3. Original o'lcham
            orig_h = await self._get_height(source)
            if not orig_h:
                return {"original": file_id}

            logger.info(f"Original height: {orig_h}px")
            orig_key = f"{orig_h}p"
            results: Dict[str, str] = {}

            # 4. Original transcoding
            await self._notify(
                status_callback, str(gt("💾 Original tayyorlanmoqda..."))
            )
            try:
                out_orig = os.path.join(tmp, "orig.mp4")
                await self._transcode(source, out_orig, orig_h)
                fid = await self._upload(
                    out_orig, user_id, f"Original ({orig_key})", thumb_path
                )
                results["original"] = fid or file_id
                results[orig_key] = fid or file_id
            except Exception as e:
                logger.error(f"Original failed: {e}", exc_info=True)
                await self._notify(
                    status_callback, str(gt("⚠️ Xato: {e}")).format(e=str(e)[:80])
                )
                try:
                    fid = await self._upload(
                        source, user_id, f"Original ({orig_key})", thumb_path
                    )
                    results["original"] = fid or file_id
                    results[orig_key] = fid or file_id
                except Exception:
                    results["original"] = file_id
                    results[orig_key] = file_id

            # 5. Qo'shimcha sifatlar
            to_do = sorted(
                [(n, h) for n, h in TARGET_QUALITIES.items() if h < orig_h],
                key=lambda x: x[1],
                reverse=True,
            )
            if not to_do:
                return results

            await self._notify(
                status_callback,
                str(gt("⚙️ {n} ta sifat tayyorlanmoqda...")).format(n=len(to_do)),
            )

            sem = asyncio.Semaphore(MAX_PARALLEL_WORKERS)
            tasks = [
                self._transcode_and_upload(
                    sem,
                    source,
                    tmp,
                    name,
                    h,
                    user_id,
                    i,
                    len(to_do),
                    status_callback,
                    thumb_path,
                )
                for i, (name, h) in enumerate(to_do, 1)
            ]
            for (name, _h), res in zip(
                to_do, await asyncio.gather(*tasks, return_exceptions=True)
            ):
                if isinstance(res, Exception):
                    logger.error(f"[{name}] failed: {res}")
                elif res:
                    results[name] = res

        await self._notify(
            status_callback, str(gt("✅ Tayyor! {n} ta format.")).format(n=len(results))
        )
        logger.info(f"process_video done: {list(results.keys())}")
        return results

    # ═══════════════════════════════════════════
    # THUMBNAIL TAYYORLASH
    # ═══════════════════════════════════════════

    async def _prepare_thumbnail(self, file_id: str, tmp: str) -> Optional[str]:
        """
        Telegram dan thumbnail yuklab, ustiga bot_watermark qo'yib,
        320x180 JPEG qaytaradi.
        Watermark: pastki chap burchak, thumbnail kengligining ~25%.
        """
        raw = os.path.join(tmp, "thumb_raw.jpg")
        try:
            info = await self.bot.get_file(file_id)
            await self._download(info.file_path, raw)
        except Exception as e:
            logger.warning(f"Thumbnail yuklanmadi: {e}")
            return None

        out = os.path.join(tmp, "thumb_wm.jpg")

        has_wm = os.path.isfile(WATERMARK_PATH)
        if has_wm:
            # 320x180 ga crop-fill, watermark pastki chap (~25% kenglik = 80px)
            flt = (
                "[0:v]scale=320:180:force_original_aspect_ratio=increase,"
                "crop=320:180,setsar=1[bg];"
                "[1:v]scale=80:-1[wm];"
                "[bg][wm]overlay=8:main_h-overlay_h-8[out]"
            )
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                raw,
                "-i",
                WATERMARK_PATH,
                "-filter_complex",
                flt,
                "-map",
                "[out]",
                "-vframes",
                "1",
                "-pix_fmt",
                "yuvj420p",
                "-q:v",
                "2",
                out,
            ]
        else:
            # Watermark yo'q — faqat resize
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                raw,
                "-vf",
                "scale=320:180:force_original_aspect_ratio=increase,crop=320:180",
                "-vframes",
                "1",
                "-pix_fmt",
                "yuvj420p",
                "-q:v",
                "2",
                out,
            ]

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        _, err = await proc.communicate()
        if proc.returncode != 0:
            logger.error(f"thumbnail ffmpeg xato: {err.decode()[-300:]}")
            return raw  # xato bo'lsa watermarksiz original qaytaradi
        return out

    # ═══════════════════════════════════════════
    # VIDEO TRANSCODING
    # ═══════════════════════════════════════════

    async def _transcode(self, src: str, dst: str, height: int) -> None:
        """
        1. Intro (agar mavjud) videoning o'lchamiga moslanib qo'shiladi
           (intro kesiladi/kengaytiriladi — videoning width/height asosiy)
        2. bot_watermark.png pastki chap burchakda (video kengligining 12%)
        3. Faqat video encode — thumbnail alohida _upload da beriladi
        """
        w = (height * 16 // 9) & ~1
        h = height & ~1

        # Video uchun scale (aspect ratio saqlanadi, qora padding)
        video_scale = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
        )
        # Intro uchun scale (videoning o'lchamiga to'liq moslanadi, crop)
        intro_scale = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},setsar=1,format=yuv420p"
        )

        has_intro = os.path.isfile(INTRO_PATH)
        has_wm = os.path.isfile(WATERMARK_PATH)

        # Watermark o'lchami: video kengligining 12% (minimum 60px)
        wm_w = max(60, w * 12 // 100) & ~1
        wm_f = f"scale={wm_w}:-1"
        wm_o = "overlay=10:main_h-overlay_h-10"

        logger.info(
            f"_transcode [{height}p] {w}x{h} intro={has_intro} wm={has_wm} wm_w={wm_w}px"
        )

        if has_intro:
            a_intro = await self._has_audio(INTRO_PATH)
            a_main = await self._has_audio(src)

            # Input: 0=intro, 1=video, 2=watermark(agar bor)
            inputs = ["-i", INTRO_PATH, "-i", src]
            pre = f"[0:v]{intro_scale}[v0];[1:v]{video_scale}[v1];"

            if a_intro and a_main:
                concat = "[v0][0:a][v1][1:a]concat=n=2:v=1:a=1[vc][ac]"
                audio_map = ["-map", "[ac]"]
            elif a_main:
                concat = "anullsrc=r=44100:cl=stereo[a0];[v0][a0][v1][1:a]concat=n=2:v=1:a=1[vc][ac]"
                audio_map = ["-map", "[ac]"]
            else:
                concat = "[v0][v1]concat=n=2:v=1:a=0[vc]"
                audio_map = []

            if has_wm:
                inputs += ["-i", WATERMARK_PATH]
                fc = pre + concat + f";[2:v]{wm_f}[wm];[vc][wm]{wm_o}[vout]"
                vm = ["-map", "[vout]"]
            else:
                fc = pre + concat.replace("[vc]", "[vout]").replace("[vc]", "[vout]")
                # concat da [vc] ni [vout] ga rename
                fc = pre + concat
                vm = ["-map", "[vc]"]

            cmd = (
                ["ffmpeg", "-y"]
                + inputs
                + ["-filter_complex", fc]
                + vm
                + audio_map
                + [
                    "-c:v",
                    "libx264",
                    "-crf",
                    "28",
                    "-preset",
                    "veryfast",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    dst,
                ]
            )

        else:
            # Intro yo'q
            if has_wm:
                inputs = ["-i", src, "-i", WATERMARK_PATH]
                fc = (
                    f"[0:v]{video_scale}[vs];"
                    f"[1:v]{wm_f}[wm];"
                    f"[vs][wm]{wm_o}[vout]"
                )
                cmd = (
                    ["ffmpeg", "-y"]
                    + inputs
                    + [
                        "-filter_complex",
                        fc,
                        "-map",
                        "[vout]",
                        "-map",
                        "0:a?",
                        "-c:v",
                        "libx264",
                        "-crf",
                        "28",
                        "-preset",
                        "veryfast",
                        "-c:a",
                        "copy",
                        dst,
                    ]
                )
            else:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    src,
                    "-vf",
                    video_scale,
                    "-map",
                    "0:v",
                    "-map",
                    "0:a?",
                    "-c:v",
                    "libx264",
                    "-crf",
                    "28",
                    "-preset",
                    "veryfast",
                    "-c:a",
                    "copy",
                    dst,
                ]

        logger.info(f"ffmpeg cmd: {' '.join(cmd)}")
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        _, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg [{height}p] xato:\n{err.decode()[-800:]}")

    # ═══════════════════════════════════════════
    # UPLOAD
    # ═══════════════════════════════════════════

    async def _upload(
        self,
        path: str,
        user_id: int,
        label: str,
        thumb_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        Videoni Telegram ga yuklaydi.
        thumb_path berilsa — BufferedInputFile orqali thumbnail beradi.
        (FSInputFile thumbnail uchun ba'zi aiogram versiyalarida ishlamaydi)
        """
        thumb_input = None
        if thumb_path and os.path.isfile(thumb_path):
            try:
                with open(thumb_path, "rb") as f:
                    data = f.read()
                thumb_input = BufferedInputFile(data, filename="thumb.jpg")
                logger.info(f"Thumbnail yuborilmoqda: {len(data)} bytes")
            except Exception as e:
                logger.error(f"Thumbnail o'qilmadi: {e}")

        async def send(thumb):
            return await self.bot.send_video(
                chat_id=user_id,
                video=FSInputFile(path),
                thumbnail=thumb,
                caption=f"🎞 {label}",
                disable_notification=True,
            )

        try:
            msg = await send(thumb_input)
            return msg.video.file_id if msg.video else None
        except Exception as e:
            logger.error(f"send_video failed: {e}")
            if thumb_input is not None:
                logger.warning("Thumbnail bilan xato — thumbnailsiz qayta urinish...")
                try:
                    msg = await send(None)
                    return msg.video.file_id if msg.video else None
                except Exception as e2:
                    logger.error(f"send_video retry failed: {e2}")
                    raise e2
            raise e

    # ═══════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════

    async def _transcode_and_upload(
        self,
        sem: asyncio.Semaphore,
        src: str,
        tmp: str,
        name: str,
        height: int,
        user_id: int,
        idx: int,
        total: int,
        cb: StatusCallback,
        thumb_path: Optional[str],
    ) -> Optional[str]:
        async with sem:
            out = os.path.join(tmp, f"v_{height}p.mp4")
            try:
                await self._notify(
                    cb,
                    str(gt("🔄 {n} tayyorlanmoqda ({i}/{t})...")).format(
                        n=name, i=idx, t=total
                    ),
                )
                await self._transcode(src, out, height)
                await self._notify(
                    cb,
                    str(gt("📤 {n} yuklanmoqda ({i}/{t})...")).format(
                        n=name, i=idx, t=total
                    ),
                )
                return await self._upload(out, user_id, name, thumb_path)
            except Exception as e:
                logger.error(f"[{name}] failed: {e}", exc_info=True)
                await self._notify(
                    cb, str(gt("❌ {n} o'tkazib yuborildi.")).format(n=name)
                )
                return None
            finally:
                if os.path.exists(out):
                    try:
                        os.remove(out)
                    except Exception:
                        pass

    async def _download(self, file_path: str, dest: str) -> None:
        token = self.bot.token
        bot_id = token.split(":")[0] if ":" in token else token
        local = "/var/lib/telegram-bot-api"

        if os.path.isfile(file_path):
            await asyncio.to_thread(shutil.copy2, file_path, dest)
            return
        for candidate in [
            os.path.join(local, token, file_path.lstrip("/")),
            os.path.join(local, bot_id, file_path.lstrip("/")),
            os.path.join(local, file_path.lstrip("/")),
        ]:
            if os.path.isfile(candidate):
                await asyncio.to_thread(shutil.copy2, candidate, dest)
                return
        await self.bot.download_file(file_path, dest)

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
    async def _notify(cb: StatusCallback, text: str) -> None:
        if cb:
            try:
                await cb(text)
            except Exception:
                pass
