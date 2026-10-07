from html import escape

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup

from bot.config import settings
from bot.db.models import User
from bot.keyboards.inline import main_menu_kb
from bot.utils.access import has_access
from bot.utils.telegram import safe_edit

router = Router()


def _welcome(user: User) -> str:
    status = (
        "🟢 <b>Premium Member</b>\n<i>You have full access to all materials.</i>"
        if has_access(user)
        else "🔴 <b>Free Tier</b>\n<i>Free samples are open. Upgrade for full access to all modules and past exams.</i>"
    )
    return (
        f"🎓 <b>Welcome to {escape(settings.university_name)} Hub!</b>\n"
        f"────────────────────────\n"
        f"Hello, <b>{escape(user.full_name or 'Student')}</b>! 👋\n\n"
        f"Your ultimate study companion is here. Access high-quality modules, slides, instructor notes, worksheets, and past exams all in one place.\n\n"
        f"<b>Your Status:</b>\n{status}\n\n"
        "👇 <b>Select an option below to start exploring:</b>"
    )


from sqlalchemy.ext.asyncio import AsyncSession
from bot.db import crud

@router.callback_query(F.data == "check_sub")
async def check_sub_success(cb: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User) -> None:
    await cb.answer("✅ Thank you for subscribing!", show_alert=True)
    await cb.message.delete()
    await cmd_start(cb.message, state, session, db_user)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, db_user: User) -> None:
    await state.clear()
    courses_dict = await crud.get_course_dict(session)
    
    intro_video_id = await crud.get_value(session, "intro_video")
    if intro_video_id:
        try:
            await message.answer_video(intro_video_id, caption=_welcome(db_user), reply_markup=main_menu_kb(has_access(db_user), courses_dict))
            return
        except Exception:
            pass # fallback to text if video fails
            
    await message.answer(_welcome(db_user), reply_markup=main_menu_kb(has_access(db_user), courses_dict))


@router.callback_query(F.data == "menu:main")
async def back_to_main(cb: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User) -> None:
    await state.clear()
    courses_dict = await crud.get_course_dict(session)
    await safe_edit(cb.message, _welcome(db_user), main_menu_kb(has_access(db_user), courses_dict))
    await cb.answer()


@router.callback_query(F.data == "user:profile")
async def show_profile(cb: CallbackQuery, db_user: User) -> None:
    status_icon = "🟢 Premium" if has_access(db_user) else "🔴 Free Tier"
    joined = db_user.created_at.strftime("%B %d, %Y")
    
    text = (
        f"👤 <b>My Profile</b>\n"
        f"────────────────────────\n"
        f"<b>Name:</b> {escape(db_user.full_name)}\n"
        f"<b>Telegram ID:</b> <code>{db_user.telegram_id}</code>\n"
        f"<b>Joined:</b> {joined}\n\n"
        f"<b>Current Plan:</b> {status_icon}\n"
        f"────────────────────────\n"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[Btn(text="⬅️ Back to Menu", callback_data="menu:main")]])
    await safe_edit(cb.message, text, kb)
    await cb.answer()


@router.callback_query(F.data == "user:help")
async def show_help(cb: CallbackQuery) -> None:
    text = (
        f"❓ <b>Help & FAQ</b>\n"
        f"────────────────────────\n"
        f"<b>Q: How do I get Full Access?</b>\n"
        f"A: Click '💎 Unlock Premium Access' on the main menu, make the payment via Telebirr or CBE, and send the screenshot. An admin will verify it shortly.\n\n"
        f"<b>Q: Can I download the materials?</b>\n"
        f"A: To protect our content, premium files cannot be forwarded or saved to your device, but you can view them instantly inside Telegram anytime!\n\n"
        f"<b>Q: I paid but I'm still on Free Tier?</b>\n"
        f"A: Verification is manual. Please allow a few hours. If it's urgent, you can reach out to the admin.\n\n"
        f"<b>Support Contact:</b> You can contact the admin if you have any issues."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[Btn(text="⬅️ Back to Menu", callback_data="menu:main")]])
    await safe_edit(cb.message, text, kb)
    await cb.answer()
