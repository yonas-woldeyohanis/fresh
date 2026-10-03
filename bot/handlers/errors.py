import logging
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent

router = Router()
log = logging.getLogger(__name__)

@router.errors()
async def global_error_handler(event: ErrorEvent):
    if isinstance(event.exception, TelegramBadRequest):
        msg = str(event.exception)
        if "query is too old" in msg or "query ID is invalid" in msg:
            # We silently ignore this as it just means the user's callback query 
            # took too long (often due to bot restart or network lag)
            log.warning(f"Ignored old callback query exception: {msg}")
            return
            
    log.exception(f"Update {event.update.update_id} caused an error:", exc_info=event.exception)
