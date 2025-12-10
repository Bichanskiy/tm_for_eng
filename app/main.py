import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.handlers.start import router as start_router
from app.handlers.help import router as help_router
from app.handlers.add_task import router as add_task_router
from app.handlers.tasks import router as tasks_router
from app.handlers.callbacks import router as callbacks_router


async def main() -> None:
    # Initialize bot and dispatcher
    bot = Bot(token=settings.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register routers
    dp.include_router(start_router)
    dp.include_router(help_router)
    dp.include_router(add_task_router)
    dp.include_router(tasks_router)
    dp.include_router(callbacks_router)

    # Skip previous updates and run polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        print('Bot is starting')
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Shutting down bot')