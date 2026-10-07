from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import crud
from bot.db.models import User
from bot.keyboards.inline import exam_courses_kb, exam_types_kb, exam_years_kb, materials_kb
from bot.utils.access import has_access
from bot.utils.telegram import safe_edit

router = Router()


@router.callback_query(F.data == "exams")
async def exams_hub(cb: CallbackQuery, session: AsyncSession) -> None:
    courses = await crud.get_course_dict(session)
    ai_enabled = await crud.get_value(session, "ai_enabled", default="true") == "true"
    await safe_edit(cb.message, "📝 <b>Past Exams Hub</b>\n\nChoose a course:", exam_courses_kb(courses, ai_enabled))
    await cb.answer()


@router.callback_query(F.data.startswith("ex:c:"))
async def exam_types(cb: CallbackQuery, session: AsyncSession) -> None:
    code = cb.data.split(":")[2]
    courses = await crud.get_course_dict(session)
    if code not in courses:
        return await cb.answer("Unknown course.", show_alert=True)
    
    stats = await crud.get_course_stats(session, code)
    mid_count = stats.get("exams_mid", 0)
    final_count = stats.get("exams_final", 0)
    
    text = f"📝 <b>{courses[code]}</b>\n────────────────────────\n<i>Contains {mid_count} Mid Exams and {final_count} Final Exams</i>\n\nSelect Exam Type:"
    await safe_edit(cb.message, text, exam_types_kb(code))
    await cb.answer()


@router.callback_query(F.data.startswith("ex:t:"))
async def exam_years(cb: CallbackQuery, session: AsyncSession) -> None:
    parts = cb.data.split(":")
    code = parts[2]
    exam_type = parts[3]
    courses = await crud.get_course_dict(session)
    if code not in courses:
        return await cb.answer("Unknown course.", show_alert=True)
        
    years = await crud.list_exam_years(session, code, exam_type)
    type_name = "Mid Exams" if exam_type == "exams_mid" else "Final Exams"
    text = f"📝 <b>{courses[code]}</b> — {type_name}\n\n" + (
        "Choose a year:" if years else "No exams uploaded yet — check back soon!"
    )
    await safe_edit(cb.message, text, exam_years_kb(code, exam_type, years))
    await cb.answer()


@router.callback_query(F.data.startswith("ex:y:"))
async def exam_list(cb: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    try:
        parts = cb.data.split(":")
        code = parts[2]
        exam_type = parts[3]
        year_i = int(parts[4])
    except (ValueError, IndexError):
        return await cb.answer()
        
    courses = await crud.get_course_dict(session)
    if code not in courses:
        return await cb.answer("Unknown course.", show_alert=True)
    items = await crud.list_exams(session, code, year_i, exam_type)
    
    type_name = "Mid Exams" if exam_type == "exams_mid" else "Final Exams"
    
    if items:
        file_word = "file" if len(items) == 1 else "files"
        text = f"📝 <b>{courses[code]}</b> — {type_name} ({year_i})\n────────────────────────\n<i>Contains {len(items)} {file_word}</i>\n\nTap an exam to receive it."
    else:
        text = f"📝 <b>{courses[code]}</b> — {type_name} ({year_i})\n────────────────────────\n\n<i>No exams found.</i>"
        
    await safe_edit(
        cb.message,
        text,
        materials_kb(items, has_access(db_user), back=f"ex:t:{code}:{exam_type}"),
    )
    await cb.answer()
