import logging
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db import crud
from bot.db.models import User
from bot.keyboards.inline import admin_review_kb, cancel_payment_kb, open_menu_kb
from bot.states import PaymentFlow
from bot.utils.access import has_access
from bot.utils.telegram import safe_edit

router = Router()
log = logging.getLogger(__name__)

PAY_TEXT = (
    "💎 <b>Unlock Premium Access</b>\n"
    "────────────────────────\n"
    "Get instant, unlimited access to all modules, past exams, and exclusive materials for a one-time payment of <b>{price} ETB</b>.\n\n"
    "<b>Payment Methods:</b>\n"
    "🏦 <b>CBE:</b> <code>{cbe}</code>\n"
    "📱 <b>Telebirr:</b> <code>{tele}</code>\n"
    "👤 <b>Name:</b> {holder}\n\n"
    "<b>Steps to Verify:</b>\n"
    "1️⃣ Send exactly <b>{price} ETB</b> to one of the accounts above.\n"
    "2️⃣ Take a clear screenshot of the transaction.\n"
    "3️⃣ Send the screenshot to me right here as a <b>photo</b>.\n\n"
    "<i>⏳ Note: Verification is done manually and usually takes a few hours. Thanks for your patience!</i>"
)


@router.callback_query(F.data == "pay:start")
async def start_payment(cb: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User) -> None:
    if has_access(db_user):
        return await cb.answer("✅ You already have full access!", show_alert=True)
    if await crud.get_pending_payment(session, db_user.telegram_id):
        return await cb.answer(
            "⏳ Your receipt is already under review. You'll get a message as soon as it's decided.",
            show_alert=True,
        )
    await state.set_state(PaymentFlow.waiting_for_receipt)
    await safe_edit(
        cb.message,
        PAY_TEXT.format(
            price=settings.price_etb,
            cbe=escape(settings.cbe_account),
            tele=escape(settings.telebirr_number),
            holder=escape(settings.account_holder),
        ),
        cancel_payment_kb(),
    )
    await cb.answer()


@router.message(PaymentFlow.waiting_for_receipt, F.photo)
async def receive_receipt(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot, db_user: User
) -> None:
    payment = await crud.create_payment(session, db_user.telegram_id, message.photo[-1].file_id)

    when = datetime.now(ZoneInfo("Africa/Addis_Ababa")).strftime("%Y-%m-%d %H:%M")
    handle = f"@{escape(db_user.username)}" if db_user.username else "—"
    caption = (
        f"🧾 <b>New payment #{payment.id}</b>\n"
        f"👤 {escape(db_user.full_name)}\n"
        f"🆔 <code>{db_user.telegram_id}</code>\n"
        f"🔗 {handle}\n"
        f"🕒 {when} (EAT)"
    )
    try:
        await bot.send_photo(
            settings.admin_chat_id,
            message.photo[-1].file_id,
            caption=caption,
            reply_markup=admin_review_kb(payment.id),
        )
    except TelegramAPIError as e:
        log.warning(f"Could not forward receipt to admin chat: {e}. Trying individual admins...")
        sent = False
        for admin_id in settings.admin_id_set:
            try:
                await bot.send_photo(
                    admin_id,
                    message.photo[-1].file_id,
                    caption=caption,
                    reply_markup=admin_review_kb(payment.id),
                )
                sent = True
            except TelegramAPIError:
                pass
        
        if not sent:
            log.exception("Could not forward receipt to ANY admin.")
            await session.rollback()
            return await message.answer("⚠️ Couldn't submit your receipt right now. Please try again in a few minutes.")

    await session.commit()
    await state.clear()
    await message.answer(
        "✅ <b>Receipt received!</b>\n\nYour transaction is now <b>pending manual review</b>. "
        "We'll message you here as soon as it's decided.",
        reply_markup=open_menu_kb(),
    )


@router.message(PaymentFlow.waiting_for_receipt)
async def wrong_input(message: Message) -> None:
    await message.answer(
        "📸 Please send your payment screenshot as a <b>photo</b> (not a file or text).\n"
        "Send /start to cancel."
    )
