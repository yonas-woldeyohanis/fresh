from collections.abc import Sequence
from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup
from bot.db.models import Material
from bot.utils.constants import CATEGORIES, COURSES

def _grid(buttons: list[Btn], cols: int) -> list[list[Btn]]:
    return [buttons[i : i + cols] for i in range(0, len(buttons), cols)]

def admin_main_kb() -> InlineKeyboardMarkup:
    rows = [
        [Btn(text="📤 Upload New Resource", callback_data="admin:upload:course")],
        [Btn(text="📂 Manage Resources", callback_data="admin:manage:course")],
        [Btn(text="🔄 Refresh Stats", callback_data="admin:dash")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_courses_kb(action: str) -> InlineKeyboardMarkup:
    rows = _grid([Btn(text=f"📚 {n}", callback_data=f"admin:{action}:cat:{c}") for c, n in COURSES.items()], 2)
    rows.append([Btn(text="⬅️ Back to Dashboard", callback_data="admin:dash")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_categories_kb(action: str, course: str) -> InlineKeyboardMarkup:
    rows = _grid([Btn(text=label, callback_data=f"admin:{action}:final:{course}:{key}") for key, label in CATEGORIES.items()], 2)
    rows.append([Btn(text="⬅️ Back to Courses", callback_data=f"admin:{action}:course")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_materials_kb(materials: Sequence[Material], course: str, category: str, page: int = 0) -> InlineKeyboardMarkup:
    # simple pagination could go here, for now list all
    rows = []
    for m in materials:
        icon = "🎁" if m.is_sample else "📄"
        rows.append([Btn(text=f"{icon} {m.title[:40]}", callback_data=f"admin:mat:{m.id}")])
    
    rows.append([Btn(text="⬅️ Back to Categories", callback_data=f"admin:manage:cat:{course}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_material_details_kb(material_id: int, course: str, category: str) -> InlineKeyboardMarkup:
    rows = [
        [Btn(text="✏️ Edit Title", callback_data=f"admin:edit:{material_id}")],
        [Btn(text="🗑️ Delete", callback_data=f"admin:del:{material_id}")],
        [Btn(text="⬅️ Back to List", callback_data=f"admin:manage:final:{course}:{category}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[Btn(text="❌ Cancel", callback_data="admin:dash")]])
