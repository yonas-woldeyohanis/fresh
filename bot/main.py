import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.db.session import engine, init_db
from bot.handlers import admin, courses, exams, materials, payment, samples, start
from bot.middlewares.access import AccessMiddleware
from bot.middlewares.db import DbSessionMiddleware, UserMiddleware
from bot.middlewares.force_sub import ForceSubMiddleware

async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    await init_db()

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Order matters: session -> user -> force_sub -> access guard
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(DbSessionMiddleware())
        observer.outer_middleware(UserMiddleware())
        observer.outer_middleware(ForceSubMiddleware())
    dp.callback_query.outer_middleware(AccessMiddleware())

    from bot.handlers import admin, courses, exams, materials, payment, samples, start, ai_tutor, errors
    
    # start first so /start always escapes the payment FSM
    dp.include_routers(
        start.router, admin.router, payment.router,
        courses.router, exams.router, samples.router, materials.router,
        ai_tutor.router, errors.router,
    )

    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
