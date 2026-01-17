from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from aiogram.types import ChatMemberUpdated
from aiogram.fsm.context import FSMContext
import database
import logging
from loader import bot
from keyboards.reply import get_main_menu

router = Router()

@router.my_chat_member()
async def leave_groups(event: ChatMemberUpdated):
    if event.chat.type in ["group", "supergroup", "channel"]:
        await bot.leave_chat(event.chat.id)
        logging.info(f"Left chat {event.chat.title} ({event.chat.id}) because I am not allowed in groups.")

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext, command: CommandObject = None):
    user_id = message.from_user.id
    database.add_user(user_id)
    
    # Check referral
    if command and command.args:
        args = command.args
        if args.startswith("ref_"):
            try:
                referrer_id = int(args.replace("ref_", ""))
                if referrer_id != user_id: # Cannot refer yourself
                    database.set_referrer(user_id, referrer_id)
                    logging.info(f"User {user_id} referred by {referrer_id}")
            except:
                pass
    
    await message.answer(
        f"👋 **Привет, {message.from_user.first_name}!**\n\n"
        "Я — специализированный бот для **отслеживания удаленных сообщений**.\n\n"
        "🕵️ **Что я делаю:**\n"
        "Я подключаюсь к вашему аккаунту и слежу за личными чатами. Если собеседник удалит или изменит сообщение, я пришлю вам уведомление.\n\n"
        "⚙️ **Как начать:**\n"
        "Нажмите кнопку **🕵️ UserBot** в меню ниже, чтобы подключить свой аккаунт.",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

from aiogram import F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@router.message(F.text == "🆘 Техподдержка")
async def cmd_support(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💻 Написать в поддержку", url="https://t.me/help_riz47")]
    ])
    await message.answer(
        "🛠 **Техническая поддержка**\n\n"
        "Если у вас возникли вопросы или проблемы, напишите нашему администратору:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
