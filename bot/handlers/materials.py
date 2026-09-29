import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery
from html import escape

from bot.config import settings
from bot.db.models import Material

router = Router()
log = logging.getLogger(__name__)


@router.callback_query(F.data == "delmsg")
async def delete_message(cb: CallbackQuery) -> None:
    await cb.message.delete()


@router.callback_query(F.data.startswith("mat:"))
async def instant_delivery(cb: CallbackQuery, bot: Bot, material: Material) -> None:
    """`material` is injected by AccessMiddleware only if the user is allowed to have it."""
    try:
        await bot.copy_message(
            chat_id=cb.from_user.id,
            from_chat_id=settings.storage_channel_id,
            message_id=material.channel_message_id,
            protect_content=True,
        )
        await cb.answer("📤 Sending…")
    except TelegramAPIError:
        log.exception("Failed to deliver material %s", material.id)
        await cb.answer("⚠️ Couldn't send this file right now. Please try again later.", show_alert=True)
