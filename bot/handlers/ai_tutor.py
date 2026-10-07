import logging
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from google import genai
from google.genai import types

from bot.config import settings
from bot.db import crud
from bot.db.models import User
from bot.states import AIChatState
from bot.utils.access import has_access
from bot.utils.constants import CATEGORIES

router = Router()
log = logging.getLogger(__name__)

def ai_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="ai:cancel")]]
    )

@router.callback_query(F.data == "ai:cancel")
async def cancel_ai(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.edit_text("🤖 AI Tutor session ended.")
    await cb.answer()

@router.message(F.text == "/cancel", AIChatState.waiting_for_question)
async def cancel_ai_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("🤖 AI Tutor session ended.")

@router.callback_query(F.data.startswith("ask_ai:"))
async def prompt_ai_tutor(cb: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User) -> None:
    code = cb.data.split(":")[1]
    courses = await crud.get_course_dict(session)
    
    if code == "main":
        course_name = "System Guide & General Tutor"
    elif code == "exams":
        course_name = "Past Exams Guide"
    else:
        course_name = courses.get(code, code)
    
    # Check rate limit
    is_premium = has_access(db_user)
    today = datetime.now(timezone.utc).date()
    
    if db_user.last_query_date != today:
        db_user.last_query_date = today
        db_user.ai_query_count = 0
        await session.commit()
        
    if not is_premium and db_user.ai_query_count >= 3:
        await cb.answer(
            "🔒 You have reached your daily limit of 3 free AI queries.\n\n"
            "Upgrade to Premium for unlimited AI tutoring!", 
            show_alert=True
        )
        return

    price = await crud.get_value(session, "price_etb") or settings.price_etb

    # Pass the entire system dictionary into state so we don't have to fetch it later
    system_knowledge = {
        "courses": list(courses.values()),
        "categories": list(CATEGORIES.values()) + ["Mid Exams", "Final Exams"],
        "premium_price": price,
    }

    await state.set_state(AIChatState.waiting_for_question)
    await state.update_data(course_name=course_name, system_knowledge=system_knowledge)
    
    limit_text = "Unlimited queries" if is_premium else f"Free daily queries remaining: {3 - db_user.ai_query_count}"
    
    await cb.message.answer(
        f"🤖 <b>AI Tutor: {course_name}</b>\n\n"
        f"Ask me anything! Whether it's an academic question, or finding a module inside this bot, I can help.\n\n"
        f"<i>({limit_text})</i>\n"
        f"Type /cancel to exit.",
        reply_markup=ai_cancel_kb()
    )
    await cb.answer()

@router.message(AIChatState.waiting_for_question, F.text)
async def handle_ai_question(message: Message, state: FSMContext, session: AsyncSession, db_user: User) -> None:
    data = await state.get_data()
    course_name = data.get("course_name", "your course")
    sys_k = data.get("system_knowledge", {})
    
    is_premium = has_access(db_user)
    today = datetime.now(timezone.utc).date()
    if db_user.last_query_date != today:
        db_user.last_query_date = today
        db_user.ai_query_count = 0
        
    if not is_premium and db_user.ai_query_count >= 3:
        await message.answer("🔒 You have reached your daily limit of 3 free AI queries. Upgrade to Premium for unlimited access!")
        await state.clear()
        return
        
    # Increment usage
    db_user.ai_query_count += 1
    await session.commit()
    
    wait_msg = await message.answer("🤖 <i>Thinking...</i>")
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        
        system_instruction = (
            f"You are a supportive, step-by-step academic tutor and system guide for a university freshman bot.\n\n"
            f"SYSTEM KNOWLEDGE & NAVIGATION:\n"
            f"- We have the following Courses: {', '.join(sys_k.get('courses', []))}.\n"
            f"- Within each course, materials are divided into: {', '.join(sys_k.get('categories', []))}.\n"
            f"- 'Past Exams' (Mid and Final) are categorized separately. Users click 'Past Exams', select a course, then select 'Mid Exams' or 'Final Exams', and then choose a specific year (2012-2017).\n"
            f"- Free Samples are available on the Main Menu.\n"
            f"- Premium Access costs {sys_k.get('premium_price', 300)} ETB and unlocks all locked files. Users can unlock it by clicking 'Unlock Premium Access' on the main menu, entering their payment info, and uploading a receipt.\n"
            f"- To use the bot, a user simply clicks the interactive buttons provided on the menus. Tell them to navigate using the inline menu buttons.\n"
            f"- If a user asks where to find a specific resource (e.g., '2014 Mid Exam for Math'), guide them to the correct path: 'Past Exams' -> 'Math' -> 'Mid Exams' -> '2014'.\n\n"
            f"TUTORING RULES:\n"
            f"- If a user asks an academic question, solve and explain it step-by-step.\n"
            f"Keep solutions structured, clear, and direct. Decline to answer irrelevant non-academic queries."
        )
        
        chat_history = data.get("chat_history", f"Context: {course_name}\n")
        chat_history += f"\nStudent: {message.text}\nAI:"
        
        import asyncio
        response = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-1.5-flash',
            contents=chat_history,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction
            )
        )
        
        ans = response.text
        chat_history += f" {ans}\n"
        await state.update_data(chat_history=chat_history)
        try:
            await wait_msg.edit_text(ans, parse_mode="Markdown")
        except TelegramBadRequest:
            await wait_msg.edit_text(ans, parse_mode=None)
        
    except Exception as e:
        log.warning(f"Gemini API failed ({e}), falling back to Groq...")
        if not settings.groq_api_key:
            await wait_msg.edit_text("⚠️ Google Gemini is currently overloaded and no backup Groq key was provided. Please try again later.")
            return
            
        try:
            from groq import AsyncGroq
            groq_client = AsyncGroq(api_key=settings.groq_api_key)
            
            chat_history = data.get("chat_history", f"Context: {course_name}\n")
            chat_history += f"\nStudent: {message.text}\nAI:"
            
            groq_resp = await groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": chat_history}
                ],
                model="llama-3.1-70b-versatile",
            )
            ans = groq_resp.choices[0].message.content
            chat_history += f" {ans}\n"
            await state.update_data(chat_history=chat_history)
            
            try:
                await wait_msg.edit_text(ans, parse_mode="Markdown")
            except TelegramBadRequest:
                await wait_msg.edit_text(ans, parse_mode=None)
            
        except Exception as groq_e:
            log.exception("Both Gemini and Groq failed")
            await wait_msg.edit_text("⚠️ Sorry, both Google and Backup AI brains are overloaded right now. Please try again later.")
