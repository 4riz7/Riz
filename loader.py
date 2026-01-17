import logging
import config
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Configure logging
logging.basicConfig(level=logging.INFO)

# Extract Bot ID for filtering loopback messages
try:
    BOT_ID = int(config.BOT_TOKEN.split(':')[0])
except:
    BOT_ID = 0

# Initialize bot, dispatcher and scheduler
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()
