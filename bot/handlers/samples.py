from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import crud
from bot.db.models import User
from bot.keyboards.inline import materials_kb
from bot.utils.access import has_access
from bot.utils.telegram import safe_edit

router = Router()


@router.callback_query(F.data == "samples")
async def open_samples(cb: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    items = await crud.list_samples(session)
    text = (
        "🎁 <b>Free Sample Materials</b>\n\nOpen to everyone — judge the quality before you buy. Tap an item:"
        if items
        else "🎁 <b>Free Sample Materials</b>\n\nNo samples uploaded yet — check back soon!"
    )
    await safe_edit(cb.message, text, materials_kb(items, has_access(db_user), back="menu:main", with_course=True))
    await cb.answer()
