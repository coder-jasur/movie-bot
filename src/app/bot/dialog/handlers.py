"""
Dialog handlers for managing channels and bots in OP menu.

This module contains all event handlers for:
- Adding/deleting channels
- Adding/deleting bots
- Toggling OP status
- Navigation between dialogs
"""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.types import Message
from aiogram_dialog import DialogManager

from src.app.database.queries.bots import BotActions
from src.app.database.queries.channels import ChannelActions
from src.app.database.queries.urls import UrlActions
from src.app.bot.states.admin.channel import OPMenu, ChannelMenu, AddChannelState, AddBotState, BotMenu, AddUrlState, UrlMenu

logger = logging.getLogger(__name__)


# ==================== CHANNEL HANDLERS ====================

async def handle_channel_forward(
        message: Message,
        _,
        dialog_manager: DialogManager
) -> None:
    """
    Process forwarded message from channel to extract channel data.

    Validates that:
    - Message is forwarded from a channel
    - Channel doesn't already exist in database
    - Stores channel data for next step

    Args:
        message: Forwarded message from channel
        dialog_manager: Current dialog state manager
    """
    session: AsyncSession = dialog_manager.middleware_data["session"]

    # Check if message is forwarded from a channel
    if not message.forward_from_chat:
        dialog_manager.dialog_data["msg_type"] = "not_forwarded"
        logger.warning("User attempted to add channel without forwarding a message")
        return

    channel_actions = ChannelActions(session)
    channel_id = message.forward_from_chat.id

    # Check if channel already exists
    try:
        existing_channel = await channel_actions.get_channel(channel_id)
        if existing_channel:
            dialog_manager.dialog_data["msg_type"] = "already_exists"
            await dialog_manager.switch_to(AddChannelState.get_channel_link)
            logger.info(f"Channel {channel_id} already exists in database")
            return
    except Exception as e:
        logger.error(f"Error checking channel existence: {e}")
        dialog_manager.dialog_data["msg_type"] = "error"
        return

    # Store channel data for next step
    channel_data = {
        "channel_name": message.forward_from_chat.full_name or "Unnamed Channel",
        "channel_id": channel_id,
        "channel_username": message.forward_from_chat.username or ""
    }
    dialog_manager.dialog_data["channel_data"] = channel_data
    logger.info(f"Channel data extracted: {channel_data['channel_name']} ({channel_id})")

    await dialog_manager.switch_to(AddChannelState.get_channel_link)


async def handle_channel_url_input(
        message: Message,
        _,
        dialog_manager: DialogManager
) -> None:
    """
    Process channel URL input and save channel to database.

    Validates URL format and combines it with previously stored channel data.

    Args:
        message: Message containing channel URL
        dialog_manager: Current dialog state manager
    """
    if not message.text:
        dialog_manager.dialog_data["msg_type"] = "error_format"
        logger.warning("User sent non-text message as channel URL")
        return

    session: AsyncSession = dialog_manager.middleware_data["session"]
    channel_actions = ChannelActions(session)
    channel_data = dialog_manager.dialog_data.get("channel_data")

    if not channel_data:
        dialog_manager.dialog_data["msg_type"] = "error"
        logger.error("Channel data not found in dialog_data")
        await dialog_manager.done()
        await dialog_manager.start(OPMenu.menu)
        return

    channel_url = message.text.strip()

    try:
        await channel_actions.add_channel(
            channel_id=channel_data["channel_id"],
            channel_name=channel_data["channel_name"],
            channel_username=channel_data["channel_username"],
            channel_url=channel_url
        )
        logger.info(
            f"✅ Channel added successfully: {channel_data['channel_name']} "
            f"({channel_data['channel_id']}) - {channel_url}"
        )

    except IntegrityError:
        logger.warning(f"Channel {channel_data['channel_id']} already exists (unique violation)")
        dialog_manager.dialog_data["msg_type"] = "already_exists"
        return

    except Exception as e:
        logger.error(f"❌ Error adding channel {channel_data['channel_id']}: {e}", exc_info=True)
        dialog_manager.dialog_data["msg_type"] = "error"
        return

    finally:
        await dialog_manager.done()


async def handle_get_channel_info(
        _,
        __,
        dialog_manager: DialogManager,
        item_id: str
) -> None:
    """
    Open channel info menu for selected channel.

    Args:
        dialog_manager: Current dialog state manager
        item_id: Channel ID as string
    """
    try:
        channel_id = int(item_id)
        logger.debug(f"Opening channel info for ID: {channel_id}")
        await dialog_manager.start(
            ChannelMenu.menu,
            data={"channel_id": channel_id}
        )
    except ValueError:
        logger.error(f"Invalid channel ID format: {item_id}")


async def handle_delete_channel(
        _,
        __,
        manager: DialogManager
) -> None:
    """
    Delete channel from database.

    Args:
        manager: Current dialog state manager
    """
    session: AsyncSession = manager.middleware_data["session"]
    channel_id = manager.dialog_data.get("channel_id")

    if not channel_id:
        logger.error("Channel ID not found in dialog_data for deletion")
        await manager.done()
        return

    channel_actions = ChannelActions(session)

    try:
        await channel_actions.delete_channel(channel_id)
        logger.info(f"✅ Channel {channel_id} deleted successfully")
    except Exception as e:
        logger.error(f"❌ Error deleting channel {channel_id}: {e}", exc_info=True)

    await manager.start(OPMenu.menu)


async def handle_toggle_channel_op_status(
        _,
        __,
        manager: DialogManager
) -> None:
    """
    Toggle channel's OP status (active/inactive).

    Switches between "True" and "False" status states.

    Args:
        manager: Current dialog state manager
    """
    session: AsyncSession = manager.middleware_data["session"]
    channel_id = manager.dialog_data.get("channel_id")

    if not channel_id:
        logger.error("Channel ID not found in dialog_data for status toggle")
        return

    channel_actions = ChannelActions(session)

    try:
        channel_data = await channel_actions.get_channel(channel_id)

        if not channel_data:
            logger.error(f"Channel {channel_id} not found in database")
            return

        # Toggle status: "True" <-> "False"
        current_status = channel_data.channel_status
        new_status = "False" if current_status == "True" else "True"

        await channel_actions.update_channel_status(new_status, channel_id)
        logger.info(
            f"✅ Channel {channel_id} status changed: {current_status} -> {new_status}"
        )

    except Exception as e:
        logger.error(f"❌ Error toggling channel {channel_id} status: {e}", exc_info=True)

    await manager.switch_to(ChannelMenu.menu)


# ==================== BOT HANDLERS ====================

async def handle_bot_username_input(
        message: Message,
        _,
        dialog_manager: DialogManager
) -> None:
    """
    Process bot username input.

    Validates that:
    - Message contains text
    - Bot doesn't already exist in database
    - Stores username for next step

    Args:
        message: Message containing bot username
        dialog_manager: Current dialog state manager
    """
    if not message.text:
        dialog_manager.dialog_data["msg_type"] = "error_format"
        logger.warning("User sent non-text message as bot username")
        return

    session: AsyncSession = dialog_manager.middleware_data["session"]
    bot_actions = BotActions(session)

    # Clean username: remove @ symbol if present
    bot_username = message.text.strip().lstrip("@")

    # Check if bot already exists
    try:
        existing_bot = await bot_actions.get_bot(bot_username)
        if existing_bot:
            dialog_manager.dialog_data["msg_type"] = "already_exists"
            logger.info(f"Bot @{bot_username} already exists in database")
            return
    except Exception as e:
        logger.error(f"Error checking bot existence: {e}")
        dialog_manager.dialog_data["msg_type"] = "error"
        return

    # Store username for next step
    dialog_manager.dialog_data["bot_username"] = bot_username
    logger.info(f"Bot username stored: @{bot_username}")

    await dialog_manager.switch_to(AddBotState.get_bot_link)


async def handle_bot_url_input(
        message: Message,
        _,
        dialog_manager: DialogManager
) -> None:
    """
    Process bot URL input.

    Args:
        message: Message containing bot URL
        dialog_manager: Current dialog state manager
    """
    if not message.text:
        dialog_manager.dialog_data["msg_type"] = "error_format"
        logger.warning("User sent non-text message as bot URL")
        return

    bot_url = message.text.strip()
    dialog_manager.dialog_data["bot_url"] = bot_url
    logger.debug(f"Bot URL stored: {bot_url}")

    await dialog_manager.switch_to(AddBotState.get_bot_name)


async def handle_default_bot_url(
        _,
        __,
        dialog_manager: DialogManager
) -> None:
    """
    Generate and set default bot URL (https://t.me/username).

    Args:
        dialog_manager: Current dialog state manager
    """
    bot_username = dialog_manager.dialog_data.get("bot_username")

    if not bot_username:
        logger.error("Bot username not found in dialog_data")
        return

    # Generate standard Telegram bot URL
    bot_url = f"https://t.me/{bot_username}"
    dialog_manager.dialog_data["bot_url"] = bot_url
    logger.info(f"Default bot URL set: {bot_url}")

    await dialog_manager.switch_to(AddBotState.get_bot_name)


async def handle_bot_name_input(
        message: Message,
        _,
        dialog_manager: DialogManager
) -> None:
    """
    Process bot display name input and save bot to database.

    Combines all previously collected data (username, URL, name) and saves to DB.

    Args:
        message: Message containing bot display name
        dialog_manager: Current dialog state manager
    """
    if not message.text:
        dialog_manager.dialog_data["msg_type"] = "error_format"
        logger.warning("User sent non-text message as bot name")
        return

    session: AsyncSession = dialog_manager.middleware_data["session"]
    bot_actions = BotActions(session)

    bot_name = message.text.strip()
    bot_username = dialog_manager.dialog_data.get("bot_username")
    bot_url = dialog_manager.dialog_data.get("bot_url")

    # Validate all required data is present
    if not bot_username or not bot_url:
        logger.error(f"Missing bot data - username: {bot_username}, url: {bot_url}")
        dialog_manager.dialog_data["msg_type"] = "error"
        await dialog_manager.done()
        await dialog_manager.start(OPMenu.menu)
        return

    try:
        await bot_actions.add_bot(
            bot_name=bot_name,
            bot_username=bot_username,
            bot_url=bot_url
        )
        logger.info(f"✅ Bot added successfully: {bot_name} (@{bot_username}) - {bot_url}")

    except IntegrityError:
        logger.warning(f"Bot @{bot_username} already exists (unique violation)")
        dialog_manager.dialog_data["msg_type"] = "already_exists"
        return

    except Exception as e:
        logger.error(f"❌ Error adding bot @{bot_username}: {e}", exc_info=True)
        dialog_manager.dialog_data["msg_type"] = "error"
        return

    finally:
        await dialog_manager.done()


async def handle_get_bot_info(
        _,
        __,
        dialog_manager: DialogManager,
        item_id: str
) -> None:
    """
    Open bot info menu for selected bot.

    Args:
        dialog_manager: Current dialog state manager
        item_id: Bot username
    """
    logger.debug(f"Opening bot info for username: {item_id}")
    await dialog_manager.start(
        BotMenu.menu,
        data={"bot_username": item_id}
    )


async def handle_delete_bot(
        _,
        __,
        manager: DialogManager
) -> None:
    """
    Delete bot from database.

    Args:
        manager: Current dialog state manager
    """
    session: AsyncSession = manager.middleware_data["session"]
    bot_username = manager.dialog_data.get("bot_username")

    if not bot_username:
        logger.error("Bot username not found in dialog_data for deletion")
        await manager.done()
        return

    bot_actions = BotActions(session)

    try:
        await bot_actions.delete_bot(bot_username)
        logger.info(f"✅ Bot @{bot_username} deleted successfully")
    except Exception as e:
        logger.error(f"❌ Error deleting bot @{bot_username}: {e}", exc_info=True)

    await manager.done()


async def handle_toggle_bot_op_status(
        _,
        __,
        manager: DialogManager
) -> None:
    """
    Toggle bot's OP status (active/inactive).

    Switches between "True" and "False" status states.

    Args:
        manager: Current dialog state manager
    """
    session: AsyncSession = manager.middleware_data["session"]
    bot_username = manager.dialog_data.get("bot_username")

    if not bot_username:
        logger.error("Bot username not found in dialog_data for status toggle")
        return

    bot_actions = BotActions(session)

    try:
        bot_data = await bot_actions.get_bot(bot_username)

        if not bot_data:
            logger.error(f"Bot @{bot_username} not found in database")
            return

        # Toggle status: "True" <-> "False"
        current_status = bot_data.bot_status
        new_status = "False" if current_status == "True" else "True"

        await bot_actions.update_bot_status(new_status, bot_username)
        logger.info(
            f"✅ Bot @{bot_username} status changed: {current_status} -> {new_status}"
        )

    except Exception as e:
        logger.error(f"❌ Error toggling bot @{bot_username} status: {e}", exc_info=True)

    await manager.switch_to(BotMenu.menu)


# ==================== URL HANDLERS ====================

async def handle_url_link_input(
        message: Message,
        _,
        dialog_manager: DialogManager
) -> None:
    if not message.text:
        dialog_manager.dialog_data["msg_type"] = "error_format"
        return

    url_link = message.text.strip()
    dialog_manager.dialog_data["url_link"] = url_link

    await dialog_manager.switch_to(AddUrlState.get_url_name)


async def handle_url_name_input(
        message: Message,
        _,
        dialog_manager: DialogManager
) -> None:
    if not message.text:
        dialog_manager.dialog_data["msg_type"] = "error_format"
        return

    session: AsyncSession = dialog_manager.middleware_data["session"]
    url_actions = UrlActions(session)

    url_name = message.text.strip()
    url_link = dialog_manager.dialog_data.get("url_link")

    if not url_link:
        dialog_manager.dialog_data["msg_type"] = "error"
        await dialog_manager.done()
        await dialog_manager.start(OPMenu.menu)
        return

    try:
        await url_actions.add_url(
            url_name=url_name,
            url_link=url_link
        )
    except Exception as e:
        logger.error(f"❌ Error adding url: {e}", exc_info=True)
        dialog_manager.dialog_data["msg_type"] = "error"
        return
    finally:
        await dialog_manager.done()


async def handle_get_url_info(
        _,
        __,
        dialog_manager: DialogManager,
        item_id: str
) -> None:
    await dialog_manager.start(
        UrlMenu.menu,
        data={"url_id": item_id}
    )


async def handle_delete_url(
        _,
        __,
        manager: DialogManager
) -> None:
    session: AsyncSession = manager.middleware_data["session"]
    url_id = manager.dialog_data.get("url_id")

    if not url_id:
        await manager.done()
        return

    url_actions = UrlActions(session)

    try:
        await url_actions.delete_url(int(url_id))
    except Exception as e:
        logger.error(f"❌ Error deleting url ID {url_id}: {e}", exc_info=True)

    await manager.done()


async def handle_toggle_url_op_status(
        _,
        __,
        manager: DialogManager
) -> None:
    session: AsyncSession = manager.middleware_data["session"]
    url_id = manager.dialog_data.get("url_id")

    if not url_id:
        return

    url_actions = UrlActions(session)

    try:
        url_data = await url_actions.get_url(int(url_id))
        if not url_data:
            return

        current_status = url_data.url_status
        new_status = "False" if current_status == "True" else "True"

        await url_actions.update_url_status(new_status, int(url_id))
    except Exception as e:
        logger.error(f"❌ Error toggling url ID {url_id} status: {e}", exc_info=True)

    await manager.switch_to(UrlMenu.menu)

