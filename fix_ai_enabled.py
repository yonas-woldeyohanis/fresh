import re
import os

def replace_in_file(filename):
    with open(filename, 'r') as f:
        content = f.read()

    # Add ai_enabled query
    if 'intro_video_id =' in content:
        content = content.replace('intro_video_id = await crud.get_value(session, "intro_video")', 'intro_video_id = await crud.get_value(session, "intro_video")\n    ai_enabled = await crud.get_value(session, "ai_enabled", default="true") == "true"')
        content = content.replace('main_menu_kb(has_access(db_user), courses_dict)', 'main_menu_kb(has_access(db_user), courses_dict, ai_enabled)')
    elif 'courses_dict =' in content and 'main_menu_kb' in content:
        content = content.replace('courses_dict = await crud.get_course_dict(session)', 'courses_dict = await crud.get_course_dict(session)\n    ai_enabled = await crud.get_value(session, "ai_enabled", default="true") == "true"')
        content = content.replace('main_menu_kb(has_access(db_user), courses_dict)', 'main_menu_kb(has_access(db_user), courses_dict, ai_enabled)')

    if 'course_menu_kb(code)' in content:
        content = content.replace('course_menu_kb(code)', 'course_menu_kb(code, ai_enabled)')
        content = re.sub(r'(async def.*session: AsyncSession.*:)', r'\1\n    ai_enabled = await crud.get_value(session, "ai_enabled", default="true") == "true"', content)
        
    if 'exam_courses_kb(courses_dict)' in content:
        content = content.replace('exam_courses_kb(courses_dict)', 'exam_courses_kb(courses_dict, ai_enabled)')
        if 'ai_enabled =' not in content:
            content = content.replace('courses_dict = await crud.get_course_dict(session)', 'courses_dict = await crud.get_course_dict(session)\n    ai_enabled = await crud.get_value(session, "ai_enabled", default="true") == "true"')

    with open(filename, 'w') as f:
        f.write(content)

replace_in_file("bot/handlers/start.py")
replace_in_file("bot/handlers/courses.py")
replace_in_file("bot/handlers/exams.py")
