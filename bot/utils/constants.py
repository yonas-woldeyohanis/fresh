from bot.config import settings
COURSES = settings.courses_dict

CATEGORIES: dict[str, str] = {
    "modules": "📘 Modules",
    "slides": "📊 PPTs",
    "handwritten": "✍️ Instructor Notes",
    "worksheets": "🎯 Worksheets",
}

EXAMS_MID = "exams_mid"
EXAMS_FINAL = "exams_final"
ALL_CATEGORIES = {*CATEGORIES, EXAMS_MID, EXAMS_FINAL}
