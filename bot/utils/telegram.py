from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message


async def safe_edit(message: Message, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    """Edit the existing menu message in place (no duplicate messages)."""
    try:
        await message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
