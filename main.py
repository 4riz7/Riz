import asyncio
import logging
import os
import database
from loader import bot, dp, scheduler
from handlers import setup_routers
from services.userbot_manager import ub_manager

async def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Initialize Database
    database.init_db()
    
    # Write PID for update script
    pid = os.getpid()
    with open("bot.pid", "w") as f:
        f.write(str(pid))

    # Setup Routers
    setup_routers(dp)

    from services.backup import create_backup
    
    # Setup Scheduler
    scheduler.add_job(ub_manager.check_deleted_messages, "interval", seconds=60, max_instances=2)
    # Automatic Backup every 6 hours
    scheduler.add_job(create_backup, "interval", hours=6)
    scheduler.start()
    
    # Run immediate backup on startup (to ensure it works)
    await create_backup()
    
    # Start saved user sessions
    sessions = database.get_all_sessions()
    for user_id, session_str in sessions:
        await ub_manager.start_client(user_id, session_str)
    
    logging.info("Starting Aiogram Bot (UserBot Only Mode)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")
