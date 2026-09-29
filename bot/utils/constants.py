from bot.config import settings
COURSES = settings.courses_dict

CATEGORIES: dict[str, str] = {
    "modules": "📘 Modules",
    "slides": "📊 PPTs",
    "handwritten": "✍️ Instructor Notes",
    "worksheets": "🎯 Worksheets",
}

EXAMS = "exams"
ALL_CATEGORIES = {*CATEGORIES, EXAMS}
