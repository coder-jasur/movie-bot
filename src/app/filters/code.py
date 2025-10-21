from tracemalloc import BaseFilter

from aiogram.types import Message


class Code(BaseFilter):
    async def __call__(self, message: Message) -> bool | dict:
        if message.text and message.text.isdigit():
            return {"code": int(message.text)}
        return False
