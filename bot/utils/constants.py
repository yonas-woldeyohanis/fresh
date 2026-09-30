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

def format_course_stats(stats: dict[str, int]) -> str:
    if not stats:
        return "<i>No materials uploaded yet.</i>"
    
    parts = []
    for cat_key, label in CATEGORIES.items():
        if count := stats.get(cat_key, 0):
            # E.g. "📘 Modules" -> "Modules"
            clean_label = label.split(' ', 1)[-1]
            parts.append(f"{count} {clean_label}")
            
    if mid := stats.get(EXAMS_MID, 0):
        parts.append(f"{mid} Mid Exams")
    if final := stats.get(EXAMS_FINAL, 0):
        parts.append(f"{final} Final Exams")
        
    if not parts:
        return "<i>No materials uploaded yet.</i>"
    
    return "Contains: " + ", ".join(parts)
