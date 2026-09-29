import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.filters import Command, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db import crud
from bot.db.models import PaymentStatus
from bot.keyboards.inline import open_menu_kb
from bot.keyboards.admin_kb import (
    admin_main_kb, admin_courses_kb, admin_categories_kb,
    admin_materials_kb, admin_material_details_kb, admin_cancel_kb
)
from bot.states import AdminMode
from bot.utils.constants import ALL_CATEGORIES, COURSES, EXAMS

router = Router()
log = logging.getLogger(__name__)

class IsAdmin(Filter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return bool(event.from_user) and event.from_user.id in settings.admin_id_set

def _admin_label(cb: CallbackQuery) -> str:
    u = cb.from_user
    return f"@{escape(u.username)}" if u.username else escape(u.full_name)


# ---------- Dashboard & Navigation ----------
@router.message(IsAdmin(), F.chat.type == "private", Command("admin"))
async def admin_dashboard(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await send_dashboard(message, session)

@router.callback_query(IsAdmin(), F.data == "admin:dash")
async def cb_admin_dashboard(cb: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await send_dashboard(cb.message, session, is_edit=True)
    await cb.answer()

async def send_dashboard(message: Message, session: AsyncSession, is_edit: bool = False):
    stats = await crud.get_analytics(session)
    text = (
        f"👑 <b>{escape(settings.university_name)} - Admin Panel</b>\n\n"
        f"👥 <b>Total Students:</b> {stats['total_users']}\n"
        f"✅ <b>Verified Students:</b> {stats['verified_users']}\n"
        f"📚 <b>Total Materials:</b> {stats['total_materials']}\n"
        f"💰 <b>Approved Payments:</b> {stats['approved_payments']}\n"
        f"⏳ <b>Pending Payments:</b> {stats['pending_payments']}\n\n"
        "<i>Select an action below:</i>"
    )
    if is_edit:
        await message.edit_text(text, reply_markup=admin_main_kb())
    else:
        await message.answer(text, reply_markup=admin_main_kb())


# ---------- Upload Flow ----------
@router.callback_query(IsAdmin(), F.data.startswith("admin:upload:"))
async def admin_upload_flow(cb: CallbackQuery, state: FSMContext) -> None:
    parts = cb.data.split(":")
    step = parts[2]
    
    if step == "course":
        await cb.message.edit_text("📚 <b>Select a Course to upload to:</b>", reply_markup=admin_courses_kb("upload"))
    elif step == "cat":
        course = parts[3]
        await cb.message.edit_text(f"📁 <b>{course}</b> - Select Category:", reply_markup=admin_categories_kb("upload", course))
    elif step == "final":
        course, category = parts[3], parts[4]
        await state.set_state(AdminMode.uploading)
        await state.update_data(course=course, category=category)
        await cb.message.edit_text(
            f"🚀 <b>Upload Mode Active</b>\n\n"
            f"<b>Course:</b> {course}\n<b>Category:</b> {category}\n\n"
            "👉 Send or forward any files now. The bot will automatically use their file names as titles.\n\n"
            "<i>Click Cancel or send /admin when you are finished.</i>",
            reply_markup=admin_cancel_kb()
        )
    await cb.answer()

@router.message(IsAdmin(), F.chat.type == "private", AdminMode.uploading, F.content_type.in_({"document", "photo", "video", "audio"}))
async def bulk_upload_material(message: Message, bot: Bot, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    course = data["course"]
    category = data["category"]

    title = "Untitled"
    if message.document and message.document.file_name:
        title = message.document.file_name.rsplit(".", 1)[0].replace("_", " ")
    elif message.video and message.video.file_name:
        title = message.video.file_name.rsplit(".", 1)[0].replace("_", " ")
    elif message.audio and message.audio.file_name:
        title = message.audio.file_name.rsplit(".", 1)[0].replace("_", " ")

    try:
        copied = await bot.copy_message(
            chat_id=settings.storage_channel_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=escape(f"{course} • {category} • {title}"),
        )
    except TelegramAPIError as e:
        return await message.answer(f"❌ Couldn't store the file: <code>{escape(str(e))}</code>")

    m = await crud.add_material(
        session, course_code=course, category=category, title=title,
        channel_message_id=copied.message_id
    )
    await message.answer(f"✅ Added <b>#{m.id}</b>: {escape(title)}\n<i>(Keep sending files, or /admin to exit)</i>")


# ---------- Manage Flow ----------
@router.callback_query(IsAdmin(), F.data.startswith("admin:manage:"))
async def admin_manage_flow(cb: CallbackQuery, session: AsyncSession) -> None:
    parts = cb.data.split(":")
    step = parts[2]

    if step == "course":
        await cb.message.edit_text("📚 <b>Select a Course to manage:</b>", reply_markup=admin_courses_kb("manage"))
    elif step == "cat":
        course = parts[3]
        await cb.message.edit_text(f"📁 <b>{course}</b> - Select Category:", reply_markup=admin_categories_kb("manage", course))
    elif step == "final":
        course, category = parts[3], parts[4]
        materials = await crud.list_materials(session, course, category)
        if not materials:
            await cb.message.edit_text(f"📂 <b>{course} • {category}</b>\n\nNo materials found here.", reply_markup=admin_categories_kb("manage", course))
        else:
            await cb.message.edit_text(f"📂 <b>{course} • {category}</b>\nSelect a file:", reply_markup=admin_materials_kb(materials, course, category))
    await cb.answer()

@router.callback_query(IsAdmin(), F.data.startswith("admin:mat:"))
async def admin_material_details(cb: CallbackQuery, session: AsyncSession) -> None:
    mat_id = int(cb.data.split(":")[2])
    m = await crud.get_material(session, mat_id)
    if not m:
        return await cb.answer("❌ Material not found in DB.", show_alert=True)
    
    text = (
        f"📄 <b>File Details</b>\n\n"
        f"<b>ID:</b> #{m.id}\n"
        f"<b>Title:</b> {escape(m.title)}\n"
        f"<b>Course:</b> {m.course_code}\n"
        f"<b>Category:</b> {m.category}\n"
        f"<b>Storage ID:</b> {m.channel_message_id}"
    )
    await cb.message.edit_text(text, reply_markup=admin_material_details_kb(m.id, m.course_code, m.category))
    await cb.answer()

@router.callback_query(IsAdmin(), F.data.startswith("admin:del:"))
async def admin_delete_material(cb: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    mat_id = int(cb.data.split(":")[2])
    m = await crud.get_material(session, mat_id)
    if not m:
        return await cb.answer("Already deleted.", show_alert=True)
    
    # Try deleting from channel
    try:
        await bot.delete_message(chat_id=settings.storage_channel_id, message_id=m.channel_message_id)
    except TelegramAPIError as e:
        log.warning(f"Could not delete message {m.channel_message_id} from channel: {e}")
        # Ignore error, maybe it was already manually deleted

    await crud.delete_material(session, mat_id)
    await cb.message.edit_text(f"✅ Deleted <b>{escape(m.title)}</b>.\n\nIt is removed from the bot and the storage channel.", reply_markup=admin_cancel_kb())
    await cb.answer("Deleted!")

@router.callback_query(IsAdmin(), F.data.startswith("admin:edit:"))
async def admin_edit_title_start(cb: CallbackQuery, state: FSMContext) -> None:
    mat_id = int(cb.data.split(":")[2])
    await state.set_state(AdminMode.editing_title)
    await state.update_data(material_id=mat_id)
    await cb.message.edit_text("✏️ Send the new title for this file:", reply_markup=admin_cancel_kb())
    await cb.answer()

@router.message(IsAdmin(), F.chat.type == "private", AdminMode.editing_title, F.text)
async def admin_edit_title_finish(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    mat_id = data["material_id"]
    new_title = message.text.strip()
    
    m = await crud.get_material(session, mat_id)
    if m:
        await crud.update_material_title(session, mat_id, new_title)
        await message.answer(f"✅ Title updated to:\n<b>{escape(new_title)}</b>", reply_markup=admin_cancel_kb())
    else:
        await message.answer("❌ Material not found.")
    await state.clear()


# ---------- Payment Decisions ----------
@router.callback_query(F.data.regexp(r"^pay:(ok|no):\d+$"))
async def review_payment(cb: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if cb.from_user.id not in settings.admin_id_set:
        return await cb.answer("⛔ You're not authorized to review payments.", show_alert=True)

    _, action, pid = cb.data.split(":")
    approve = action == "ok"
    payment = await crud.decide_payment(session, int(pid), PaymentStatus.APPROVED if approve else PaymentStatus.REJECTED, cb.from_user.id)
    if payment is None:
        return await cb.answer("This payment was already processed.", show_alert=True)

    if approve:
        await crud.verify_user(session, payment.telegram_id)
    await session.commit()

    label = "✅ Approved" if approve else "❌ Rejected"
    await cb.message.edit_caption(caption=f"{cb.message.html_text}\n\n<b>{label} by {_admin_label(cb)}</b>", reply_markup=None)

    if approve:
        text = "🎉 <b>Payment approved!</b>\n\nFull access is unlocked — all modules, slides, notes and exams are yours."
    else:
        text = "❌ <b>We couldn't verify your payment.</b>\n\nPlease re-check your transaction details and tap 💳 Unlock Full Access to submit a clearer receipt."
    try:
        await bot.send_message(payment.telegram_id, text, reply_markup=open_menu_kb())
    except (TelegramForbiddenError, TelegramAPIError):
        pass
    await cb.answer("Done")
