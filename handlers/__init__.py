from aiogram import Dispatcher
from .start import router as start_router
from .userbot import router as userbot_router
from .admin import router as admin_router
from .payment import router as payment_router

def setup_routers(dp: Dispatcher):
    dp.include_router(start_router)
    dp.include_router(userbot_router)
    dp.include_router(payment_router)
    dp.include_router(admin_router)
