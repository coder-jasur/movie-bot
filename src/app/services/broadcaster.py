import asyncio
import logging
from typing import Optional, Union

from aiogram import Bot, types
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import (
    InputMediaAnimation,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.common.i18n import lazy_gettext as _
from src.app.database.models import User
from src.app.database.queries.user import UserActions

logger = logging.getLogger(__name__)


class Broadcaster:

    def __init__(
        self,
        bot: Bot,
        session: AsyncSession,
        admin_id: int,
        broadcasting_message: Message | None = None,
        from_chat_id: int | None = None,
        message_id: int | None = None,
        reply_markup: types.InlineKeyboardMarkup | None = None,
        album: list[Message] | None = None,
        batch_size: int = 5000,
        sleep_seconds: float = 0.05,
        exclude_vip: bool = False,
    ):
        self._bot = bot
        self._session = session
        self.broadcasting_message = broadcasting_message
        self.from_chat_id = from_chat_id or (
            broadcasting_message.chat.id if broadcasting_message else None
        )
        self.message_id = message_id or (
            broadcasting_message.message_id if broadcasting_message else None
        )
        self.reply_markup = reply_markup or (
            broadcasting_message.reply_markup if broadcasting_message else None
        )
        self.album = album
        self.admin_id = admin_id
        self.batch_size = batch_size
        self.sleep_seconds = sleep_seconds
        self.exclude_vip = exclude_vip
        self.message_per_second = (
            int(1 / self.sleep_seconds) if sleep_seconds > 0 else 25
        )

        # Статистика для отчетов
        self.sent_messages_count = 0
        self.failed_messages_count = 0
        self.processed_batches = 0
        self.total_processed = 0

        # Списки различных типов блокировок
        self.blocked_users: list[int] = []  # Пользователи, заблокировавшие бота
        self.deleted_users: list[int] = []  # Пользователи, чей аккаунт удален
        self.deactivated_users: list[int] = (
            []
        )  # Пользователи, чей аккаунт был деактивирован
        self.limited_users: list[int] = (
            []
        )  # Пользователи, чей аккаунт временно ограничен

        self.total_blocked_users: int = (
            0  # Количество пользователей, заблокировавшие бота
        )
        self.total_deleted_users: int = (
            0  # Количество пользователей, чей аккаунт удален
        )
        self.total_deactivated_users: int = (
            0  # Количество пользователей, чей аккаунт был деактивирован
        )
        self.total_limited_users: int = (
            0  # Количество пользователей, чей аккаунт временно ограничен
        )

        # Validate input parameters
        if not (self.message_id or self.album):
            raise ValueError(
                "Either message_id/broadcasting_message or album must be provided"
            )
        if self.message_id and self.album:
            raise ValueError(
                "Only one of broadcasting_message or album should be provided"
            )

    async def _send_info_message(self, info_message_text: str) -> types.Message:
        """Send status message to admin"""
        return await self._bot.send_message(
            self.admin_id,
            info_message_text.format(
                sent=0,
                failed=0,
                blocked=0,
                deleted=0,
                limited=0,
                deactivated=0,
                batches=0,
            ),
        )

    async def _update_info_message(
        self, info_message: Message, info_message_text: str, include_total: bool = False
    ) -> None:
        """
        Update status message with current progress

        Args:
            info_message: Message to update
            info_message_text: Template for status message
            include_total: Whether to include total processed users count
        """
        try:
            text = info_message_text.format(
                sent=self.sent_messages_count,
                failed=self.failed_messages_count,
                blocked=len(self.blocked_users),
                deleted=len(self.deleted_users),
                limited=len(self.limited_users),
                deactivated=len(self.deactivated_users),
                batches=self.processed_batches,
            )

            if include_total:
                text += f"\n\n{_('Всего обработано')}: {self.total_processed} {_('пользователей')}"

            await info_message.edit_text(text)

        except Exception as e:
            logger.error(f"Error updating info message: {e}")

    async def broadcast(self) -> tuple[int, int, int, int]:
        """
        Start broadcasting messages to all users

        Returns:
            Tuple of (blocked_count, deleted_count, limited_count, deactivated_count)
        """
        info_message_text = (
            f"{_('Отправка сообщений')}: {{sent}}\n"
            f"{_('Не удалось отправить')}: {{failed}}\n"
            f"{_('Заблокировали')}: {{blocked}}\n"
            f"{_('Удаленных аккаунтов')}: {{deleted}}\n"
            f"{_('Ограниченных')}: {{limited}}\n"
            f"{_('Деактивированных')}: {{deactivated}}\n"
            f"{_('Обработано пачек')}: {{batches}}"
        )

        # Инициализация сообщения со статусом
        info_message = await self._send_info_message(info_message_text)

        try:
            logger.info("Starting batch broadcast")

            # Обрабатываем пользователей пачками
            users_actions = UserActions(self._session)
            async for user_ids, offset in users_actions.iterate_user_ids(
                self.batch_size, exclude_vip=self.exclude_vip
            ):
                # Обрабатываем текущую пачку пользователей
                await self._process_batch(user_ids, info_message, info_message_text)

                self.processed_batches += 1
                self.total_processed += len(user_ids)

                # Обновляем сообщение о статусе после каждой пачки
                await self._update_info_message(info_message, info_message_text)

                # Если есть заблокированные пользователи, помечаем их в базе данных
                if (
                    self.blocked_users
                    or self.deleted_users
                    or self.limited_users
                    or self.deactivated_users
                ):
                    await self._mark_user_statuses(
                        blocked_user_ids=self.blocked_users,
                        deleted_user_ids=self.deleted_users,
                        limited_users_ids=self.limited_users,
                        deactivated_user_ids=self.deactivated_users,
                    )

                    # Обновляем число пользователей,
                    # которые заблокировали бота или удалили аккаунт
                    # или чей аккаунт был деактивирован
                    self.total_blocked_users += len(self.blocked_users)
                    self.total_deleted_users += len(self.deleted_users)
                    self.total_limited_users += len(self.limited_users)
                    self.total_deactivated_users += len(self.deactivated_users)

                    # Очищаем списки, так как уже обработали
                    self.blocked_users = []
                    self.deleted_users = []
                    self.limited_users = []
                    self.deactivated_users = []

            logger.info(
                f"Broadcasting completed: {self.sent_messages_count} sent, "
                f"{self.failed_messages_count} failed, "
                f"{self.total_blocked_users} blocked, "
                f"{self.total_deleted_users} deleted, "
                f"{self.total_limited_users} limited, "
                f"{self.total_deactivated_users} deactivated accounts, "
                f"{self.processed_batches} batches processed"
            )

        except Exception as e:
            logger.error(f"Broadcasting error: {e}")
            await self._bot.send_message(
                self.admin_id, f"{_('Ошибка при рассылке')}: {e}"
            )
        finally:
            # Финальное обновление статуса
            try:
                await self._update_info_message(
                    info_message, info_message_text, include_total=True
                )
            except Exception as e:
                logger.error(f"Error in final update: {e}")

            # Удаляем предпросмотр рассылки
            await self._delete_preview()

            # Помечаем оставшихся заблокированных пользователей
            if (
                self.blocked_users
                or self.deleted_users
                or self.limited_users
                or self.deactivated_users
            ):
                await self._mark_user_statuses(
                    blocked_user_ids=self.blocked_users,
                    deleted_user_ids=self.deleted_users,
                    limited_users_ids=self.limited_users,
                    deactivated_user_ids=self.deactivated_users,
                )

        return (
            self.total_blocked_users,
            self.total_deleted_users,
            self.total_limited_users,
            self.total_deactivated_users,
        )

    async def _process_batch(
        self, user_ids: list[int], info_message: Message, info_message_text: str
    ) -> None:
        """
        Process a batch of users

        Args:
            user_ids: List of user IDs to process
            info_message: Status message to update
            info_message_text: Template for status message
        """
        batch_sent = 0
        batch_failed = 0
        should_update = False

        for user_id in user_ids:
            result = await self._send_broadcasting_message(user_id)

            if result is True:
                self.sent_messages_count += 1
                batch_sent += 1
            else:
                self.failed_messages_count += 1
                batch_failed += 1

                if isinstance(result, int):
                    self.blocked_users.append(user_id)
                elif result == "deactivated":
                    self.deactivated_users.append(user_id)
                elif result == "limited":
                    self.limited_users.append(user_id)
                elif result == "deleted":
                    self.deleted_users.append(user_id)

            await asyncio.sleep(self.sleep_seconds)

            # Периодическое обновление статуса внутри пачки
            # Обновляем каждые N сообщений
            if batch_sent > 0 and batch_sent % (self.message_per_second * 4) == 0:
                should_update = True
            # Обновляем каждые N ошибок
            elif batch_failed > 0 and batch_failed % (self.message_per_second * 2) == 0:
                should_update = True

            if should_update:
                await self._update_info_message(info_message, info_message_text)
                should_update = False

    async def _send_broadcasting_message(self, user_id: int) -> Union[bool, int, str]:
        """
        Send message to a specific user

        Args:
            user_id: User ID to send message to

        Returns:
            True if successful,
            user_id if blocked by user,
            "deleted" if account deleted,
            "limited" if account limited,
            "deactivated" if account deactivated,
            False otherwise
        """
        try:
            if self.message_id:
                await self._bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=self.from_chat_id,
                    message_id=self.message_id,
                    reply_markup=self.reply_markup,
                )
            else:
                await self._bot.send_media_group(
                    chat_id=user_id, media=self._make_sendable_album(self.album)
                )
            logger.debug(f"Target [ID:{user_id}]: message sent successfully")
            return True

        except TelegramForbiddenError as e:
            # Проверяем причину ошибки для определения статуса
            error_message = str(e).lower()
            if "deactivated" in error_message:
                logger.warning(f"Target [ID:{user_id}]: account deactivated")
                return "deactivated"
            elif "limited" in error_message:
                logger.warning(f"Target [ID:{user_id}]: account limited")
                return "limited"
            elif "not found" in error_message:
                logger.warning(f"Target [ID:{user_id}]: account deleted")
                return "deleted"
            else:
                logger.warning(f"Target [ID:{user_id}]: blocked by user")
                return user_id

        except TelegramBadRequest as err:
            logger.error(f"Target [ID:{user_id}]: wrong request - {err}")
            return False

        except TelegramRetryAfter as e:
            logger.warning(
                f"Target [ID:{user_id}]: Flood limit exceeded. Sleeping {e.retry_after} seconds."
            )
            await asyncio.sleep(e.retry_after)
            return await self._send_broadcasting_message(user_id)

        except TelegramAPIError as e:
            logger.error(f"Target [ID:{user_id}]: API error - {e}")

        except Exception as e:
            logger.error(f"Target [ID:{user_id}]: unexpected error - {e}")

        return False

    async def _update_user_status(
        self, user_ids: list[int], status: str = "blocked"
    ) -> None:
        """
        Update user status in database

        Args:
            user_ids: List of user IDs to update
            status: Status to set (blocked, deleted, limited, deactivated)
        """
        if not user_ids:
            return

        stmt = update(User).where(User.tg_id.in_(user_ids)).values(status=status)

        try:
            await self._session.execute(stmt)
            await self._session.commit()
            logger.debug(f"Updated {len(user_ids)} users to status: {status}")
        except Exception as e:
            logger.error(f"Failed to update user status: {e}")
            raise

    async def _mark_user_statuses(
        self,
        blocked_user_ids: list[int],
        deleted_user_ids: list[int],
        limited_users_ids: list[int],
        deactivated_user_ids: list[int],
    ) -> None:
        """
        Mark users with appropriate statuses in database

        Args:
            blocked_user_ids: List of IDs for users who blocked the bot
            deleted_user_ids: List of IDs for users who deleted their accounts
            limited_users_ids: List of IDs for users who limited
            deactivated_user_ids: List of IDs for users who deactivated
        """
        try:
            # Обработка заблокированных пользователей
            if blocked_user_ids:
                stmt = (
                    update(User)
                    .where(User.tg_id.in_(blocked_user_ids))
                    .values(status="blocked")
                )
                await self._session.execute(stmt)
                logger.info(f"Marked {len(blocked_user_ids)} users as BLOCKED")

            # Обработка удаленных аккаунтов
            if deleted_user_ids:
                stmt = (
                    update(User)
                    .where(User.tg_id.in_(deleted_user_ids))
                    .values(status="deleted")
                )
                await self._session.execute(stmt)
                logger.info(f"Marked {len(deleted_user_ids)} users as DELETED")

            # Обработка ограниченных аккаунтов
            if limited_users_ids:
                stmt = (
                    update(User)
                    .where(User.tg_id.in_(limited_users_ids))
                    .values(status="limited")
                )
                await self._session.execute(stmt)
                logger.info(f"Marked {len(limited_users_ids)} users as LIMITED")

            # Обработка деактивированных аккаунтов
            if deactivated_user_ids:
                stmt = (
                    update(User)
                    .where(User.tg_id.in_(deactivated_user_ids))
                    .values(status="deactivated")
                )
                await self._session.execute(stmt)
                logger.info(f"Marked {len(deactivated_user_ids)} users as DEACTIVATED")

            await self._session.commit()

        except Exception as e:
            logger.error(f"Failed to mark user statuses: {e}")
            await self._session.rollback()
            raise

    async def _delete_preview(self) -> None:
        """Delete preview messages from admin chat"""
        try:
            if self.message_id:
                await self._bot.delete_message(
                    chat_id=self.admin_id, message_id=self.message_id
                )
            elif self.album:
                await self._bot.delete_messages(
                    chat_id=self.admin_id,
                    message_ids=[message.message_id for message in self.album],
                )
        except Exception as e:
            logger.error(f"Failed to delete preview: {e}")

    def _make_sendable_album(self, album: list[Message]) -> list[
        Union[
            InputMediaPhoto,
            InputMediaVideo,
            InputMediaAnimation,
            InputMediaDocument,
            InputMediaAudio,
        ]
    ]:
        """Convert message album to sendable media group"""
        if not album:
            raise ValueError("Album is empty")

        media_list = []
        for message in album:
            media = self._make_album_media(message)
            if media:
                media_list.append(media)

        if not media_list:
            raise ValueError("No valid media found in album")

        return media_list

    @staticmethod
    def _make_album_media(
        message: types.Message,
    ) -> Optional[
        Union[
            InputMediaPhoto,
            InputMediaVideo,
            InputMediaAnimation,
            InputMediaDocument,
            InputMediaAudio,
        ]
    ]:
        """Convert single message to appropriate InputMedia type"""
        try:
            if message.content_type == types.ContentType.PHOTO:
                return InputMediaPhoto(
                    media=message.photo[-1].file_id,
                    caption=(
                        message.html_text if hasattr(message, "html_text") else None
                    ),
                    has_spoiler=(
                        message.has_media_spoiler
                        if hasattr(message, "has_media_spoiler")
                        else None
                    ),
                )
            elif message.content_type == types.ContentType.VIDEO:
                return InputMediaVideo(
                    media=message.video.file_id,
                    caption=(
                        message.html_text if hasattr(message, "html_text") else None
                    ),
                    has_spoiler=(
                        message.has_media_spoiler
                        if hasattr(message, "has_media_spoiler")
                        else None
                    ),
                )
            elif message.content_type == types.ContentType.ANIMATION:
                return InputMediaAnimation(
                    media=message.animation.file_id,
                    caption=(
                        message.html_text if hasattr(message, "html_text") else None
                    ),
                    has_spoiler=(
                        message.has_media_spoiler
                        if hasattr(message, "has_media_spoiler")
                        else None
                    ),
                )
            elif message.content_type == types.ContentType.DOCUMENT:
                return InputMediaDocument(
                    media=message.document.file_id,
                    caption=(
                        message.html_text if hasattr(message, "html_text") else None
                    ),
                )
            elif message.content_type == types.ContentType.AUDIO:
                return InputMediaAudio(
                    media=message.audio.file_id,
                    caption=(
                        message.html_text if hasattr(message, "html_text") else None
                    ),
                )
            else:
                logger.warning(f"Unsupported content type: {message.content_type}")
                return None

        except Exception as e:
            logger.error(f"Error creating media object: {e}")
            return None
