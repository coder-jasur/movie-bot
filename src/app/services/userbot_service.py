import logging
import os
from typing import Optional

from pyrogram import Client

from src.app.core.config import load_config

logger = logging.getLogger(__name__)
settings = load_config()


class UserbotService:
    """
    Celery + asyncio.run() muhitida xavfsiz ishlash uchun
    har bir operatsiyada yangi Pyrogram Client yaratiladi.
    Bu event loop mismatch muammosini to'liq bartaraf etadi.
    """

    def __init__(self):
        self.session_string = settings.userbot_session
        self.api_id = settings.telegram_api_id
        self.api_hash = settings.telegram_api_hash

    def _is_configured(self) -> bool:
        return bool(self.session_string and self.api_id and self.api_hash)

    def _make_client(self) -> Client:
        """Har safar yangi, mustaqil Client yaratadi."""
        os.makedirs("sessions", exist_ok=True)
        return Client(
            name="sessions/userbot",
            session_string=self.session_string,
            api_id=self.api_id,
            api_hash=self.api_hash,
            in_memory=True,  # Fayl konflikti yo'q
            sleep_threshold=120,
            max_concurrent_transmissions=1,
        )

    async def find_video_in_chat(
        self,
        chat_id: int,
        movie_code: str,
        quality: str,
    ) -> Optional[str]:
        """
        Chatda #MCODE_{movie_code}_{quality} tegi bo'yicha video qidiradi.
        Topilsa file_id qaytaradi, yo'q bo'lsa None.
        """
        if not self._is_configured():
            logger.warning("Userbot sozlanmagan (find_video_in_chat).")
            return None

        import re

        search_tag = f"#MCODE_{movie_code}_{quality}"
        logger.info(f"Userbot: {search_tag} qidirilmoqda (chat={chat_id})")

        try:
            async with self._make_client() as client:
                async for message in client.get_chat_history(chat_id, limit=100):
                    if not message.video:
                        continue
                    caption = message.caption or ""
                    clean_caption = re.sub(r"<[^>]+>", "", caption)
                    if search_tag in caption or search_tag in clean_caption:
                        logger.info(
                            f"Userbot: topildi — {quality} -> {message.video.file_id}"
                        )
                        return message.video.file_id

            logger.info(f"Userbot: so'nggi 100 xabarda topilmadi: {search_tag}")
            return None

        except Exception as e:
            logger.error(f"Userbot find_video_in_chat xato: {e}", exc_info=True)
            return None

    async def send_video(
        self,
        chat_id: int,
        video_path: str,
        caption: str,
        thumb_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        Videoni Userbot (Premium) orqali yuboradi — 4 GB gacha.
        Muvaffaqiyatli bo'lsa file_id qaytaradi, xato bo'lsa None.
        """
        if not self._is_configured():
            logger.error("Userbot sozlanmagan (send_video).")
            return None

        if not os.path.exists(video_path):
            logger.error(f"Userbot send_video: fayl topilmadi: {video_path}")
            return None

        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        logger.info(
            f"Userbot: video yuborilmoqda: {video_path} "
            f"({file_size_mb:.1f} MB) -> chat={chat_id}"
        )

        last_pct = [-5]  # list — nonlocal o'rniga (Python 3.8 compat)

        def progress(current, total):
            if total > 0:
                pct = (current / total) * 100
                if pct - last_pct[0] >= 5:
                    logger.info(
                        f"Userbot yuklash: {pct:.1f}% "
                        f"({current / 1024 / 1024:.1f} / {total / 1024 / 1024:.1f} MB)"
                    )
                    last_pct[0] = pct

        try:
            async with self._make_client() as client:
                msg = await client.send_video(
                    chat_id=chat_id,
                    video=video_path,
                    caption=caption,
                    thumb=(
                        thumb_path
                        if thumb_path and os.path.exists(thumb_path)
                        else None
                    ),
                    progress=progress,
                )

            if msg and msg.video:
                logger.info(f"Userbot yuklash OK: {msg.video.file_id}")
                return msg.video.file_id

            logger.error("Userbot send_video: msg.video = None qaytdi.")
            return None

        except Exception as e:
            logger.error(f"Userbot send_video xato: {e}", exc_info=True)
            return None

    # ── Eski singleton API bilan moslik uchun (zarur bo'lmasa o'chirish mumkin) ──
    async def close(self):
        """
        Endi singleton client yo'q, shuning uchun bu metod hech narsa qilmaydi.
        Mavjud kodni buzmaslik uchun saqlab qolindi.
        """
        pass


# Singleton instance (faqat konfiguratsiya uchun; client har safar yangidan ochiladi)
userbot_service = UserbotService()
