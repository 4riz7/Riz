import os
import shutil
import datetime
import logging
import asyncio
from aiogram.types import FSInputFile
from config import ADMIN_ID
from loader import bot

DB_PATH = "bot_database.db"

async def create_backup():
    """
    Creates a copy of the database and sends it to the Admin.
    """
    try:
        if not os.path.exists(DB_PATH):
            logging.error("Backup failed: Database file not found!")
            return

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        backup_filename = f"backup_{timestamp}.db"
        
        # Create a local copy first
        shutil.copy2(DB_PATH, backup_filename)
        
        # Send to Admin
        file_to_send = FSInputFile(backup_filename)
        caption = (
            f"💾 **Автоматический бэкап базы данных**\n"
            f"📅 Дата: `{timestamp}`\n"
            f"📂 Файл: `{backup_filename}`\n\n"
            f"⚠️ Сохраните этот файл! В нем все подписки и сессии."
        )
        
        try:
            await bot.send_document(ADMIN_ID, file_to_send, caption=caption, parse_mode="Markdown")
            logging.info(f"✅ Backup sent to Admin ID {ADMIN_ID}")
        except Exception as e:
            logging.error(f"❌ Failed to send backup to Telegram: {e}")
        
        # Clean up local backup file to save space
        try:
            os.remove(backup_filename)
        except:
            pass
            
    except Exception as e:
        logging.error(f"Critical Backup Error: {e}")
