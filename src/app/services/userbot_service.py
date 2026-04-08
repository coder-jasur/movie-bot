import logging
from typing import Optional

from pyrogram import Client, types

from src.app.core.config import load_config

logger = logging.getLogger(__name__)
settings = load_config()


class UserbotService:
    def __init__(self):
        self.session_string = settings.userbot_session
        self.api_id = settings.telegram_api_id
        self.api_hash = settings.telegram_api_hash
        self.client: Optional[Client] = None

    async def _get_client(self) -> Optional[Client]:
        if not self.session_string or not self.api_id or not self.api_hash:
            logger.warning("Userbot settings not properly configured.")
            return None

        if self.client is None:
            self.client = Client(
                name="movie_bot_userbot",
                session_string=self.session_string,
                api_id=self.api_id,
                api_hash=self.api_hash,
                in_memory=True,
            )
            await self.client.start()
        return self.client

    async def find_video_in_chat(
        self,
        chat_id: int,
        movie_code: str,
        quality: str,
    ) -> Optional[str]:
        client = await self._get_client()
        if not client:
            return None

        try:
            search_tag = f"#MCODE_{movie_code}_{quality}"
            logger.info(f"Searching for {search_tag} in chat {chat_id}")

            import re

            async for message in client.get_chat_history(chat_id, limit=100):
                if not message.video:
                    continue

                caption = message.caption or ""
                # HTML tag larni tozalab tekshirish
                clean_caption = re.sub(r"<[^>]+>", "", caption)

                if search_tag in caption or search_tag in clean_caption:
                    logger.info(f"Found via tag: {quality} -> {message.video.file_id}")
                    return message.video.file_id

            logger.info(f"Tag not found in last 100 messages: {search_tag}")
            return None
        except Exception as e:
            logger.error(f"Userbot search failed: {e}")
            return None

    async def send_video(
        self,
        chat_id: int,
        video_path: str,
        caption: str,
        thumb_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        Videoni Userbot orqali yuboradi (Premium akkaunt bilan 4GB gacha).
        """
        client = await self._get_client()
        if not client:
            logger.error("Userbot client not available for send_video.")
            return None

        try:
            logger.info(f"Userbot uploading video: {video_path} to {chat_id}")

            async def progress(current, total):
                if total > 0:
                    pct = (current / total) * 100
                    if int(pct) % 10 == 0:  # Har 10% da log chiqaramiz
                        logger.info(
                            f"Userbot Upload: {pct:.1f}% ({current/(1024*1024):.1f} / {total/(1024*1024):.1f} MB)"
                        )

            msg = await client.send_video(
                chat_id=chat_id,
                video=video_path,
                caption=caption,
                thumb=thumb_path,
                progress=progress,
            )

            if msg and msg.video:
                logger.info(f"Userbot upload success: {msg.video.file_id}")
                return msg.video.file_id

            return None
        except Exception as e:
            logger.error(f"Userbot send_video failed: {e}")
            return None

    async def close(self):
        if self.client:
            await self.client.stop()
            self.client = None


# Singleton instance
userbot_service = UserbotService()
