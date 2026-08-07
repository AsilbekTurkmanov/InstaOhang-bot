import time
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, limit_seconds: float = 1.5):
        super().__init__()
        self.limit_seconds = limit_seconds
        self.user_timestamps = {}

    async def __call__(self, handler, event, data):
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id:
            now = time.time()
            last_time = self.user_timestamps.get(user_id, 0)
            if now - last_time < self.limit_seconds:
                if isinstance(event, CallbackQuery):
                    await event.answer("⚠️ Iltimos, biroz kuting!", show_alert=True)
                return
            self.user_timestamps[user_id] = now

        return await handler(event, data)
