from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup

from bot.db.models import Material
from bot.utils.constants import CATEGORIES, COURSES


def _grid(buttons: list[Btn], cols: int) -> list[list[Btn]]:
    return [buttons[i : i + cols] for i in range(0, len(buttons), cols)]


def _back(data: str, text: str = "⬅️ Back") -> list[Btn]:
    return [Btn(text=text, callback_data=data)]


def main_menu_kb(has_access: bool) -> InlineKeyboardMarkup:
    rows = _grid([Btn(text=f"📚 {n}", callback_data=f"course:{c}") for c, n in COURSES.items()], 2)
    rows.append([Btn(text="🎁 Free Samples", callback_data="samples"), Btn(text="📝 Past Exams", callback_data="exams")])
    
    bottom_row = [Btn(text="👤 My Profile", callback_data="user:profile"), Btn(text="❓ Help & FAQ", callback_data="user:help")]
    rows.append(bottom_row)

    if not has_access:
        rows.append([Btn(text="💎 Unlock Premium Access", callback_data="pay:start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def course_menu_kb(code: str) -> InlineKeyboardMarkup:
    rows = _grid([Btn(text=label, callback_data=f"cat:{code}:{key}") for key, label in CATEGORIES.items()], 2)
    rows.append(_back("menu:main"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def materials_kb(
    items: Sequence[Material], has_access: bool, back: str, with_course: bool = False
) -> InlineKeyboardMarkup:
    rows = []
    for m in items:
        icon = "🎁" if m.is_sample else ("📄" if has_access else "🔒")
        label = f"{icon} {m.course_code} · {m.title}" if with_course else f"{icon} {m.title}"
        rows.append([Btn(text=label[:60], callback_data=f"mat:{m.id}")])
    rows.append(_back(back))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def exam_courses_kb() -> InlineKeyboardMarkup:
    rows = _grid([Btn(text=f"📚 {n}", callback_data=f"ex:c:{c}") for c, n in COURSES.items()], 2)
    rows.append(_back("menu:main"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def exam_years_kb(code: str, years: Sequence[int]) -> InlineKeyboardMarkup:
    rows = _grid([Btn(text=f"📅 {y}", callback_data=f"ex:y:{code}:{y}") for y in years], 3)
    rows.append(_back("exams"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_payment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_back("menu:main", "❌ Cancel")])


def open_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[Btn(text="📚 Open Menu", callback_data="menu:main")]])


def admin_review_kb(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                Btn(text="✅ Approve", callback_data=f"pay:ok:{payment_id}"),
                Btn(text="❌ Reject", callback_data=f"pay:no:{payment_id}"),
            ]
        ]
    )
