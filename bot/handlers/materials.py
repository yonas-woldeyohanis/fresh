import io
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, BufferedInputFile
from html import escape

from bot.config import settings
from bot.db.models import Material
from bot.db import crud
from bot.keyboards.inline import watermark_options_kb
from bot.utils.watermark import apply_watermark

router = Router()
log = logging.getLogger(__name__)


@router.callback_query(F.data == "delmsg")
async def delete_message(cb: CallbackQuery) -> None:
    await cb.message.delete()


@router.callback_query(F.data.startswith("mat:"))
async def prompt_watermark(cb: CallbackQuery, material: Material) -> None:
    """`material` is injected by AccessMiddleware only if the user is allowed to have it."""
    # If the file has a file_id (from our new system), we can offer watermarking
    if material.file_id:
        text = (
            f"📄 <b>{escape(material.title)}</b>\n\n"
            "Would you like to stamp your personal Telegram ID onto this document before downloading? "
            "(Takes a few seconds ⏳)"
        )
        await cb.message.answer(text, reply_markup=watermark_options_kb(material.id))
        await cb.answer()
    else:
        # Legacy items without file_id get instant delivery
        await execute_instant_delivery(cb, cb.bot, material)


@router.callback_query(F.data.startswith("dl:nowm:"))
async def instant_delivery(cb: CallbackQuery, bot: Bot, material: Material) -> None:
    await cb.message.delete()
    await execute_instant_delivery(cb, bot, material)


@router.callback_query(F.data.startswith("dl:wm:"))
async def watermark_delivery(cb: CallbackQuery, bot: Bot, material: Material) -> None:
    await cb.message.edit_text("⏳ <i>Downloading and applying your watermark... Please wait...</i>")
    try:
        file = await bot.get_file(material.file_id)
        # Download bytes
        mem = io.BytesIO()
        await bot.download_file(file.file_path, destination=mem)
        pdf_bytes = mem.getvalue()
        
        # Apply watermark
        watermark_text = f"@{cb.from_user.username}" if cb.from_user.username else str(cb.from_user.id)
        stamped_bytes = apply_watermark(pdf_bytes, watermark_text)
        
        # Send back
        input_file = BufferedInputFile(stamped_bytes, filename=f"{material.title}.pdf")
        
        await bot.send_document(
            chat_id=cb.from_user.id,
            document=input_file,
            caption=f"✅ <b>{escape(material.title)}</b>\n💧 Watermarked for {watermark_text}",
            protect_content=True
        )
        await cb.message.delete()
    except Exception as e:
        log.exception("Watermarking failed")
        await cb.message.edit_text("⚠️ <i>Failed to apply watermark. Sending original file...</i>")
        await execute_instant_delivery(cb, bot, material)


async def execute_instant_delivery(cb: CallbackQuery, bot: Bot, material: Material) -> None:
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
