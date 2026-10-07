import os

for filename in [
    "bot/handlers/start.py",
    "bot/handlers/courses.py",
    "bot/handlers/admin.py",
    "bot/handlers/exams.py"
]:
    with open(filename, 'r') as f:
        content = f.read()
    
    content = content.replace(
        'await crud.get_value(session, "ai_enabled", default="true")',
        '(await crud.get_value(session, "ai_enabled") or "true")'
    )
    
    with open(filename, 'w') as f:
        f.write(content)
