from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import crud
from bot.db.models import User
from bot.keyboards.inline import course_menu_kb, materials_kb
from bot.utils.access import has_access
from bot.utils.constants import CATEGORIES, format_course_stats
from bot.utils.telegram import safe_edit

router = Router()


@router.callback_query(F.data.startswith("course:"))
async def open_course(cb: CallbackQuery, session: AsyncSession) -> None:
    ai_enabled = (await crud.get_value(session, "ai_enabled") or "true") == "true"
    code = cb.data.split(":")[1]
    courses = await crud.get_course_dict(session)
    if code not in courses:
        return await cb.answer("Unknown course.", show_alert=True)
        
    stats = await crud.get_course_stats(session, code)
    stats_text = format_course_stats(stats)
    
    await safe_edit(
        cb.message, 
        f"📚 <b>{courses[code]}</b>\n────────────────────────\n{stats_text}\n\nChoose a resource type below:", 
        course_menu_kb(code, ai_enabled)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("cat:"))
async def open_category(cb: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    ai_enabled = (await crud.get_value(session, "ai_enabled") or "true") == "true"
    try:
        _, code, cat = cb.data.split(":")
    except ValueError:
        return await cb.answer()
        
    courses = await crud.get_course_dict(session)
    if code not in courses or cat not in CATEGORIES:
        return await cb.answer("Unknown category.", show_alert=True)

    items = await crud.list_materials(session, code, cat)
    header = f"{CATEGORIES[cat]} — <b>{courses[code]}</b>\n────────────────────────"
    if items:
        file_word = "file" if len(items) == 1 else "files"
        text = f"{header}\n<i>Contains {len(items)} {file_word}</i>\n\nTap any item below to receive it directly in chat."
    else:
        text = f"{header}\n\n<i>Nothing uploaded yet — check back soon!</i>"
    await safe_edit(cb.message, text, materials_kb(items, has_access(db_user), back=f"course:{code}"))
    await cb.answer()
