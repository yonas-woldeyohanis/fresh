import asyncio
from bot.db.session import session_factory
from sqlalchemy import text

async def main():
    async with session_factory() as session:
        await session.execute(text("UPDATE materials SET category = 'exams_final' WHERE category = 'exams'"))
        await session.commit()
        print("Migrated existing exams to exams_final")

if __name__ == "__main__":
    asyncio.run(main())
