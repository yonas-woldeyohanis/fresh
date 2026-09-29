import asyncio
from bot.db.session import engine
from bot.db.models import Base

async def main():
    print("Connecting to DB...")
    async with engine.begin() as conn:
        print("Dropping old tables...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Creating new tables...")
        await conn.run_sync(Base.metadata.create_all)
    print("Done! Database is ready for watermarking.")

if __name__ == "__main__":
    asyncio.run(main())
