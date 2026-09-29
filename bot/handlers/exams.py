from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import crud
from bot.db.models import User
from bot.keyboards.inline import exam_courses_kb, exam_years_kb, materials_kb
from bot.utils.access import has_access
from bot.utils.telegram import safe_edit

router = Router()


@router.callback_query(F.data == "exams")
async def exams_hub(cb: CallbackQuery, session: AsyncSession) -> None:
    courses = await crud.get_course_dict(session)
    await safe_edit(cb.message, "📝 <b>Past Exams Hub</b>\n\nChoose a course:", exam_courses_kb(courses))
    await cb.answer()


@router.callback_query(F.data.startswith("ex:c:"))
async def exam_years(cb: CallbackQuery, session: AsyncSession) -> None:
    code = cb.data.split(":")[2]
    courses = await crud.get_course_dict(session)
    if code not in courses:
        return await cb.answer("Unknown course.", show_alert=True)
    years = await crud.list_exam_years(session, code)
    text = f"📝 <b>{courses[code]}</b> — past exams\n\n" + (
        "Choose a year:" if years else "No exams uploaded yet — check back soon!"
    )
    await safe_edit(cb.message, text, exam_years_kb(code, years))
    await cb.answer()


@router.callback_query(F.data.startswith("ex:y:"))
async def exam_list(cb: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    try:
        _, _, code, year = cb.data.split(":")
        year_i = int(year)
    except ValueError:
        return await cb.answer()
        
    courses = await crud.get_course_dict(session)
    if code not in courses:
        return await cb.answer("Unknown course.", show_alert=True)
    items = await crud.list_exams(session, code, year_i)
    await safe_edit(
        cb.message,
        f"📝 <b>{courses[code]}</b> — {year_i}\n\nTap an exam to receive it.",
        materials_kb(items, has_access(db_user), back=f"ex:c:{code}"),
    )
    await cb.answer()
