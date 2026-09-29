import asyncio
from bot.db.session import session_factory, init_db
from bot.db import crud
from bot.config import settings

async def main():
    print("Initializing Database Tables...")
    await init_db()
    print("Migrating courses to database...")
    async with session_factory() as session:
        # settings.courses_dict reads from the old .env COURSES string
        for code, name in settings.courses_dict.items():
            print(f"Adding {code}: {name}...")
            # Ignore if already exists (basic try-except)
            try:
                await crud.add_course(session, code, name)
            except Exception:
                pass
        print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
