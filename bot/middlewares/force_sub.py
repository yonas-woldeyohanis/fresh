import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import settings

log = logging.getLogger(__name__)

class ForceSubMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        
        if not settings.force_sub_channel_id or not settings.force_sub_channel_link:
            return await handler(event, data)
            
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)
            
        if user.id in settings.admin_id_set:
            return await handler(event, data)
            
        bot: Bot = data["bot"]
        
        # If it's a callback query for checking sub, let it pass through to the handler (or we can handle it here)
        if isinstance(event, CallbackQuery) and event.data == "check_sub":
            # Handled directly below or passed through
            pass

        try:
            member = await bot.get_chat_member(chat_id=settings.force_sub_channel_id, user_id=user.id)
            if member.status in ("member", "administrator", "creator"):
                return await handler(event, data)
        except Exception as e:
            log.warning(f"Failed to check membership for {user.id} in {settings.force_sub_channel_id}: {e}")
            # If the bot is not an admin in the channel, it will fail.
            # We might want to just let them pass if the bot is misconfigured.
            pass
            
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📢 Subscribe to Channel", url=settings.force_sub_channel_link)],
                [InlineKeyboardButton(text="✅ I have subscribed", callback_data="check_sub")]
            ]
        )
        
        text = "⚠️ <b>Access Denied</b>\n\nYou must subscribe to our official channel to use this bot!"
        
        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb)
        elif isinstance(event, CallbackQuery):
            if event.data == "check_sub":
                await event.answer("❌ You haven't subscribed yet!", show_alert=True)
            else:
                await event.message.answer(text, reply_markup=kb)
                await event.answer()
                
        return # Drop the update
