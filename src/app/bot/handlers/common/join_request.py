from aiogram import Router
from aiogram.types import ChatJoinRequest
import logging

logger = logging.getLogger(__name__)

join_request_router = Router()

@join_request_router.chat_join_request()
async def handle_join_request(request: ChatJoinRequest):
    """
    Automatically approves any incoming chat join request.
    This ensures users who send a request to a private channel/group 
    are immediately accepted and can pass the mandatory subscription check.
    """
    try:
        await request.approve()
        logger.info(f"✅ Auto-approved join request from {request.from_user.id} to chat {request.chat.id}")
    except Exception as e:
        logger.error(f"❌ Failed to auto-approve join request from {request.from_user.id}: {e}")
