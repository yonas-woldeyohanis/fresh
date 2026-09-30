from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.db import crud
from bot.db.session import session_factory


class DbSessionMiddleware(BaseMiddleware):
    """One DB session per update; commits on success, rolls back on error."""

    async def __call__(
        self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with session_factory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise


class UserMiddleware(BaseMiddleware):
    """Registers/refreshes the user row and exposes it to handlers as `db_user`."""

    async def __call__(
        self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user and not tg_user.is_bot:
            # Optimize: Only perform a heavy UPSERT on new messages or if user is missing
            # Callback queries (button clicks) just do a fast SELECT to check verify status
            db_user = None
            from aiogram.types import Message
            if isinstance(event, Message):  # if it's a message, upsert to update name/username
                db_user = await crud.upsert_user(
                    data["session"], tg_user.id, tg_user.username, tg_user.full_name
                )
            else:
                db_user = await crud.get_user(data["session"], tg_user.id)
                if not db_user:
                    db_user = await crud.upsert_user(
                        data["session"], tg_user.id, tg_user.username, tg_user.full_name
                    )
            data["db_user"] = db_user
            
        return await handler(event, data)
