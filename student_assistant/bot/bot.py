import os
import logging
import sys
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from .handlers.start import start_router
from .handlers.faq import faq_router
from .handlers.gaps import gaps_router

from dotenv import load_dotenv
load_dotenv()

async def main():
    session = AiohttpSession(proxy=os.environ.get("PROXY_URL"))
    bot = Bot(token=os.environ.get("BOT_TOKEN"), session=session)
    dp = Dispatcher()

    dp.include_routers(
        gaps_router,
        start_router,
        faq_router,
    )
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())