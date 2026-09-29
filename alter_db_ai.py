import asyncio
from bot.db.session import engine
from sqlalchemy import text

async def alter_db():
    print("Altering DB to add AI tracking columns...")
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN ai_query_count INTEGER DEFAULT 0;"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN last_query_date TIMESTAMP WITH TIME ZONE;"))
            print("Successfully added AI columns to users table!")
        except Exception as e:
            print(f"Notice: {e}")
            print("Columns might already exist or another error occurred.")

if __name__ == "__main__":
    asyncio.run(alter_db())
