from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery

from bot.db import crud
from bot.utils.access import has_access


class AccessMiddleware(BaseMiddleware):
    """Blocks delivery of any non-sample material for unverified students."""

    async def __call__(
        self, handler: Callable[[CallbackQuery, dict[str, Any]], Awaitable[Any]], event: CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        if event.data and (event.data.startswith("mat:") or event.data.startswith("dl:")):
            try:
                # Both 'mat:123' and 'dl:wm:123' or 'dl:nowm:123'
                material_id = int(event.data.split(":")[-1])
            except (IndexError, ValueError):
                await event.answer("Invalid item.", show_alert=True)
                return None

            material = await crud.get_material(data["session"], material_id)
            if material is None:
                await event.answer("This item is no longer available.", show_alert=True)
                return None

            user = data.get("db_user")
            if not material.is_sample and (user is None or not has_access(user)):
                await event.answer(
                    "🔒 This material is locked.\n\nGo back to the main menu and tap "
                    "💳 Unlock Full Access to get everything. Free samples are open to all!",
                    show_alert=True,
                )
                return None

            data["material"] = material
        return await handler(event, data)
