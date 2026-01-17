import asyncio
import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import config
import database
from loader import bot
from states import Form

router = Router()

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("У вас нет прав администратора.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Рассылка всем", callback_data="broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="🎟 Сгенерировать промо (7д)", callback_data="gen_promo_7")],
        [InlineKeyboardButton(text="🎟 Сгенерировать промо (30д)", callback_data="gen_promo_30")]
    ])
    await message.answer("Админ-панель:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("gen_promo_"))
async def generate_promo(callback: types.CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("У вас нет прав.")
        return
    
    days = int(callback.data.split("_")[2])
    import secrets
    code = f"RZ-{secrets.token_hex(4).upper()}"
    database.add_promo_code(code, days)
    
    await callback.message.answer(f"✅ **Промокод на {days} дней создан:**\n\n`{code}`", parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("У вас нет прав.")
        return
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")]
    ])
    await callback.message.edit_text("✍️ **Введите сообщение для рассылки всем пользователям:**\n\nМожете использовать форматирование (жирный, курсив и т.д.).", reply_markup=kb, parse_mode="Markdown")
    await state.set_state(Form.waiting_for_broadcast)
    await callback.answer()

@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await cmd_admin(callback.message) # Return to main admin menu
    await callback.answer("Рассылка отменена")

@router.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("У вас нет прав.")
        return
    
    total_users = database.get_user_count()
    active_sessions = len(database.get_all_sessions())
    
    msg = (
        "📊 **Статистика Бота**\n\n"
        f"👤 Всего пользователей в БД: **{total_users}**\n"
        f"🔌 Подключено UserBot сессий: **{active_sessions}**"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]])
    await callback.message.edit_text(msg, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "admin_back")
async def back_to_admin(callback: types.CallbackQuery):
    await cmd_admin(callback.message)

@router.message(Form.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    users = database.get_all_users()
    count = 0
    blocked = 0
    
    status_msg = await message.answer(f"🚀 Начинаю рассылку на {len(users)} пользователей...")
    
    for user_id in users:
        try:
            # Copy message to preserve formatting and content (photos, video, etc.)
            await message.copy_to(user_id)
            count += 1
            await asyncio.sleep(0.05) # Rate limit safety
        except Exception as e:
            blocked += 1
            logging.error(f"Failed to send to {user_id}: {e}")
            
    await status_msg.edit_text(
        f"✅ **Рассылка завершена!**\n\n"
        f"📨 Доставлено: {count}\n"
        f"🚫 Не доставлено (блок): {blocked}"
    )
    await state.clear()
