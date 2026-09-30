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
    admin_materials_kb, admin_material_details_kb, admin_cancel_kb,
    admin_back_dash_kb, admin_exam_years_kb
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
async def admin_upload_flow(cb: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    parts = cb.data.split(":")
    step = parts[2]
    
    if step == "course":
        courses_dict = await crud.get_course_dict(session)
        await cb.message.edit_text("📚 <b>Select a Course to upload to:</b>", reply_markup=admin_courses_kb("upload", courses_dict))
    elif step == "cat":
        course = parts[3]
        if course == "sample":
            # skip category selection for samples
            await state.set_state(AdminMode.uploading)
            await state.update_data(course="sample", category="sample")
            await cb.message.edit_text(
                f"🚀 <b>Free Samples Upload Active</b>\n\n"
                "👉 Send or forward any files now.\n\n"
                "<i>Click Cancel or send /admin when you are finished.</i>",
                reply_markup=admin_cancel_kb()
            )
        else:
            await cb.message.edit_text(f"📁 <b>{course}</b> - Select Category:", reply_markup=admin_categories_kb("upload", course))
    elif step == "examyear":
        course = parts[3]
        await cb.message.edit_text(f"📝 <b>{course}</b> - Select Exam Year:", reply_markup=admin_exam_years_kb("upload", course))
    elif step == "final":
        course, category = parts[3], parts[4]
        
        display_cat = category
        if category.startswith("exams_"):
            display_cat = f"Exams ({category.split('_')[1]})"
            
        await state.set_state(AdminMode.uploading)
        await state.update_data(course=course, category=category)
        await cb.message.edit_text(
            f"🚀 <b>Upload Mode Active</b>\n\n"
            f"<b>Course:</b> {course}\n<b>Category:</b> {display_cat}\n\n"
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
    file_id = None
    if message.document and message.document.file_name:
        title = message.document.file_name.rsplit(".", 1)[0].replace("_", " ")
        file_id = message.document.file_id
    elif message.video and message.video.file_name:
        title = message.video.file_name.rsplit(".", 1)[0].replace("_", " ")
        file_id = message.video.file_id
    elif message.audio and message.audio.file_name:
        title = message.audio.file_name.rsplit(".", 1)[0].replace("_", " ")
        file_id = message.audio.file_id
    elif message.photo:
        title = "Photo"
        file_id = message.photo[-1].file_id

    # Temporary UI state
    wait_msg = await message.answer("⏳ <i>Uploading to storage...</i>")

    try:
        copied = await bot.copy_message(
            chat_id=settings.storage_channel_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=escape(f"{course} • {category} • {title}"),
        )
    except TelegramAPIError as e:
        await wait_msg.delete()
        return await message.answer(f"❌ Couldn't store the file: <code>{escape(str(e))}</code>")

    exam_year = None
    db_category = category
    if category.startswith("exams_"):
        db_category = "exams"
        exam_year = int(category.split("_")[1])

    m = await crud.add_material(
        session, course_code=course, category=db_category, title=title,
        channel_message_id=copied.message_id, file_id=file_id, 
        exam_year=exam_year, is_sample=(course == "sample")
    )
    await wait_msg.edit_text(f"✅ Added <b>#{m.id}</b>: {escape(title)}\n<i>(Keep sending files, or /admin to exit)</i>")


# ---------- Manage Flow ----------
@router.callback_query(IsAdmin(), F.data.startswith("admin:manage:"))
async def admin_manage_flow(cb: CallbackQuery, session: AsyncSession) -> None:
    parts = cb.data.split(":")
    step = parts[2]

    if step == "course":
        courses_dict = await crud.get_course_dict(session)
        await cb.message.edit_text("📚 <b>Select a Course to manage:</b>", reply_markup=admin_courses_kb("manage", courses_dict))
    elif step == "cat":
        course = parts[3]
        if course == "sample":
            items = await crud.list_samples(session)
            if not items:
                await cb.message.edit_text("📂 <b>Free Samples</b>\nNothing uploaded yet.", reply_markup=admin_back_dash_kb())
            else:
                await cb.message.edit_text("📂 <b>Free Samples</b>", reply_markup=admin_materials_kb(items, course, "sample"))
        else:
            await cb.message.edit_text(f"📁 <b>{course}</b> - Select Category:", reply_markup=admin_categories_kb("manage", course))
    elif step == "examyear":
        course = parts[3]
        await cb.message.edit_text(f"📝 <b>{course}</b> - Select Exam Year:", reply_markup=admin_exam_years_kb("manage", course))
    elif step == "final":
        course, category = parts[3], parts[4]
        if category.startswith("exams_"):
            year = int(category.split("_")[1])
            materials = await crud.list_exams(session, course, year)
        else:
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
    
    await cb.message.edit_text(f"⏳ <i>Deleting <b>{escape(m.title)}</b>...</i>")
    
    # Try deleting from channel
    try:
        await bot.delete_message(chat_id=settings.storage_channel_id, message_id=m.channel_message_id)
    except TelegramAPIError as e:
        log.warning(f"Could not delete message {m.channel_message_id} from channel: {e}")
        # Ignore error, maybe it was already manually deleted

    await crud.delete_material(session, mat_id)
    await cb.message.edit_text(f"✅ Deleted <b>{escape(m.title)}</b>.\n\nIt is removed from the bot and the storage channel.", reply_markup=admin_back_dash_kb())
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
        await message.answer(f"✅ Title updated to:\n<b>{escape(new_title)}</b>", reply_markup=admin_back_dash_kb())
    else:
        await message.answer("❌ Material not found.")
    await state.clear()


# ---------- Payment Decisions ----------
@router.callback_query(F.data.regexp(r"^pay:(ok|no):\d+$"))
async def review_payment(cb: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if cb.from_user.id not in settings.admin_id_set:
        return await cb.answer("⛔ You're not authorized to review payments.", show_alert=True)

    await cb.message.edit_caption(caption=f"{cb.message.html_text}\n\n⏳ <i>Processing...</i>", reply_markup=None)

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

# ---------- Course Management ----------
from bot.keyboards.admin_kb import admin_course_management_kb, admin_edit_course_kb

@router.callback_query(IsAdmin(), F.data == "admin:courses:list")
async def admin_list_courses(cb: CallbackQuery, session: AsyncSession) -> None:
    courses = await crud.get_course_dict(session)
    await cb.message.edit_text("🏫 <b>Manage Courses</b>\nSelect a course to edit or add a new one:", reply_markup=admin_course_management_kb(courses))

@router.callback_query(IsAdmin(), F.data == "admin:course:add")
async def admin_add_course_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.message.edit_text("➕ <b>Add New Course</b>\n\nPlease enter a short code for the course (e.g., MATH101). No spaces allowed:", reply_markup=admin_cancel_kb())
    await state.set_state(AdminMode.waiting_for_course_code)

@router.message(IsAdmin(), AdminMode.waiting_for_course_code)
async def admin_add_course_code(message: Message, state: FSMContext) -> None:
    code = message.text.strip().upper().replace(" ", "")
    await state.update_data(new_course_code=code)
    await message.answer(f"✅ Code set to <b>{code}</b>.\n\nNow, enter the full display name for the course (e.g., General Physics I):", reply_markup=admin_cancel_kb())
    await state.set_state(AdminMode.waiting_for_course_name)

@router.message(IsAdmin(), AdminMode.waiting_for_course_name)
async def admin_add_course_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    name = message.text.strip()
    data = await state.get_data()
    code = data["new_course_code"]
    
    try:
        await crud.add_course(session, code, name)
        await message.answer(f"🎉 Successfully added <b>{name}</b> ({code})!", reply_markup=admin_back_dash_kb())
    except Exception:
        await message.answer(f"⚠️ Error: Course {code} might already exist.", reply_markup=admin_back_dash_kb())
    
    await state.clear()

@router.callback_query(IsAdmin(), F.data.startswith("admin:course:edit:"))
async def admin_edit_course_menu(cb: CallbackQuery, session: AsyncSession) -> None:
    code = cb.data.split(":")[3]
    courses = await crud.get_course_dict(session)
    if code not in courses:
        return await cb.answer("Course not found.", show_alert=True)
    
    await cb.message.edit_text(f"⚙️ <b>{courses[code]}</b> ({code})\nWhat would you like to do?", reply_markup=admin_edit_course_kb(code))

@router.callback_query(IsAdmin(), F.data.startswith("admin:course:rename:"))
async def admin_rename_course_start(cb: CallbackQuery, state: FSMContext) -> None:
    code = cb.data.split(":")[3]
    await cb.message.edit_text(f"✏️ Enter the new display name for <b>{code}</b>:", reply_markup=admin_cancel_kb())
    await state.update_data(edit_course_code=code)
    await state.set_state(AdminMode.editing_course_name)

@router.message(IsAdmin(), AdminMode.editing_course_name)
async def admin_rename_course(message: Message, state: FSMContext, session: AsyncSession) -> None:
    new_name = message.text.strip()
    data = await state.get_data()
    code = data["edit_course_code"]
    
    c = await crud.get_course(session, code)
    if c:
        c.name = new_name
        await session.commit()
        await message.answer(f"✅ Renamed {code} to <b>{new_name}</b>.", reply_markup=admin_back_dash_kb())
    else:
        await message.answer("⚠️ Course not found.", reply_markup=admin_back_dash_kb())
    await state.clear()

@router.callback_query(IsAdmin(), F.data.startswith("admin:course:recode:"))
async def admin_recode_course_start(cb: CallbackQuery, state: FSMContext) -> None:
    code = cb.data.split(":")[3]
    await cb.message.edit_text(
        f"🔤 Enter the new course code for <b>{code}</b> (e.g. MATH1012):\n"
        "<i>Note: This will safely update the course and all associated files.</i>", 
        reply_markup=admin_cancel_kb()
    )
    await state.update_data(edit_course_code=code)
    await state.set_state(AdminMode.editing_course_code)

@router.message(IsAdmin(), AdminMode.editing_course_code)
async def admin_recode_course(message: Message, state: FSMContext, session: AsyncSession) -> None:
    new_code = message.text.strip().upper().replace(" ", "")
    data = await state.get_data()
    old_code = data["edit_course_code"]
    
    try:
        success = await crud.update_course_code(session, old_code, new_code)
        if success:
            await message.answer(f"✅ Course code changed from <b>{old_code}</b> to <b>{new_code}</b>.", reply_markup=admin_back_dash_kb())
        else:
            await message.answer("⚠️ Course not found.", reply_markup=admin_back_dash_kb())
    except Exception as e:
        await message.answer(f"⚠️ Error: The code <b>{new_code}</b> might already exist.", reply_markup=admin_back_dash_kb())
    
    await state.clear()

@router.callback_query(IsAdmin(), F.data.startswith("admin:course:del:"))
async def admin_delete_course(cb: CallbackQuery, session: AsyncSession) -> None:
    code = cb.data.split(":")[3]
    success = await crud.delete_course(session, code)
    if success:
        await cb.message.edit_text(f"🗑️ Course <b>{code}</b> has been deleted.", reply_markup=admin_back_dash_kb())
    else:
        await cb.answer("Course not found.", show_alert=True)

@router.callback_query(IsAdmin(), F.data == "admin:intro_video")
async def admin_intro_video_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.message.edit_text(
        "🎬 <b>Set Intro Video</b>\n\n"
        "Send the video you want to use for the welcome message when students start the bot.\n"
        "<i>To remove the intro video, send the word 'remove'.</i>",
        reply_markup=admin_cancel_kb()
    )
    await state.set_state(AdminMode.waiting_for_intro_video)

@router.message(IsAdmin(), AdminMode.waiting_for_intro_video)
async def admin_intro_video_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.text and message.text.lower() == "remove":
        await crud.set_value(session, "intro_video", "")
        await message.answer("✅ Intro video removed.", reply_markup=admin_back_dash_kb())
        await state.clear()
        return

    if not message.video:
        await message.answer("⚠️ Please send a valid video file, or 'remove'.", reply_markup=admin_cancel_kb())
        return

    await crud.set_value(session, "intro_video", message.video.file_id)
    await message.answer("✅ Intro video set successfully! It will now play automatically when a new student starts the bot.", reply_markup=admin_back_dash_kb())
    await state.clear()

# ---------- Payment Settings ----------
from bot.keyboards.admin_kb import admin_payment_settings_kb

@router.callback_query(IsAdmin(), F.data == "admin:pay_settings")
async def admin_pay_settings(cb: CallbackQuery, session: AsyncSession) -> None:
    cbe = await crud.get_value(session, "cbe_account") or settings.cbe_account
    tele = await crud.get_value(session, "telebirr_number") or settings.telebirr_number
    other_banks = await crud.get_value(session, "other_banks") or "None set"
    holder = await crud.get_value(session, "account_holder") or settings.account_holder
    price = await crud.get_value(session, "price_etb") or settings.price_etb

    text = (
        "💳 <b>Payment Settings</b>\n\n"
        f"🏦 <b>CBE Account:</b> <code>{cbe}</code>\n"
        f"📱 <b>Telebirr:</b> <code>{tele}</code>\n"
        f"🌐 <b>Other Banks:</b>\n{other_banks}\n\n"
        f"👤 <b>Account Holder:</b> {holder}\n"
        f"💵 <b>Price:</b> {price} ETB\n\n"
        "Tap a button below to update these values dynamically:"
    )
    await cb.message.edit_text(text, reply_markup=admin_payment_settings_kb())

@router.callback_query(IsAdmin(), F.data.startswith("admin:paycfg:"))
async def admin_paycfg_start(cb: CallbackQuery, state: FSMContext) -> None:
    setting_key = cb.data.split(":")[2]
    
    labels = {
        "cbe_account": "CBE Account Number",
        "telebirr_number": "Telebirr Number",
        "other_banks": "Other Banks/Platforms (e.g. Awash: 12345...)",
        "account_holder": "Account Holder Name",
        "price_etb": "Price (in ETB)"
    }
    
    await cb.message.edit_text(
        f"✏️ Send the new value for <b>{labels.get(setting_key, setting_key)}</b>:", 
        reply_markup=admin_cancel_kb()
    )
    
    await state.set_state(AdminMode.waiting_for_payment_setting)
    await state.update_data(setting_key=setting_key)

@router.message(IsAdmin(), AdminMode.waiting_for_payment_setting)
async def admin_paycfg_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    val = message.text.strip()
    data = await state.get_data()
    setting_key = data["setting_key"]
    
    await crud.set_value(session, setting_key, val)
    await message.answer(f"✅ Successfully updated!", reply_markup=admin_back_dash_kb())
    await state.clear()
