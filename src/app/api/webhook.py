from fastapi import APIRouter, Request
from aiogram import types, Dispatcher, Bot

router = APIRouter()

@router.post("")
async def huna_webhook(request: Request):
    """
    Telegram update'larini qabul qilish uchun webhook endpointi.
    """
    bot: Bot = request.app.state.bot
    dp: Dispatcher = request.app.state.dp
    
    update_data = await request.json()
    update = types.Update(**update_data)
    
    # Update'ni dispatcher'ga yo'naltirish
    await dp.feed_update(bot, update)
    
    return {"ok": True}
