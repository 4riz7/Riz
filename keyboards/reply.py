from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu():
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🕵️ UserBot (Подключение)")],
        [KeyboardButton(text="👤 Профиль / Подписка")],
        [KeyboardButton(text="🆘 Техподдержка")]
    ], resize_keyboard=True)
    return kb
