import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from pyrogram import Client, errors
import config
import database
from loader import bot
from services.userbot_manager import ub_manager
from states import UserBotStates
from keyboards.reply import get_main_menu

router = Router()

# --- UserBot Setup Handlers ---

@router.message(F.text == "🕵️ UserBot (Подключение)")
@router.message(Command("userbot"))
async def cmd_userbot(message: types.Message, state: FSMContext):
    # Check Subscription
    import datetime
    expiry_str, _ = database.get_user_sub_info(message.from_user.id)
    is_active = False
    
    if expiry_str:
        try:
             if isinstance(expiry_str, (int, float)):
                 dt = datetime.datetime.fromtimestamp(expiry_str)
             else:
                 dt = datetime.datetime.fromisoformat(str(expiry_str))
             if dt > datetime.datetime.now():
                is_active = True
        except: pass
        
    if not is_active:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👤 Перейти в кошелёк/профиль", callback_data="back_to_profile")]])
        await message.answer("🔒 **Доступ закрыт**\n\nУ вас нет активной подписки или пробного периода.\nПожалуйста, активируйте их в профиле.", reply_markup=kb)
        return

    session = database.get_user_session(message.from_user.id)
    if session:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔴 Отключить", callback_data="ub_stop")]])
        await message.answer("✅ У вас уже подключен UserBot для отслеживания удаленных сообщений.", reply_markup=kb)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔑 Подключить", callback_data="ub_connect")]])
    await message.answer(
        "🕵️ **Настройка UserBot**\n\n"
        "Эта функция позволит мне видеть удаленные сообщения в ваших личных диалогах.\n"
        "Для этого мне нужно временно авторизоваться под вашим аккаунтом.\n\n"
        "Нажмите кнопку ниже, чтобы начать подключение.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "ub_stop")
async def process_ub_stop(callback: types.CallbackQuery):
    await ub_manager.stop_client(callback.from_user.id)
    database.delete_user_session(callback.from_user.id)
    await callback.message.edit_text("🔴 UserBot отключен. Данные сессии удалены.")
    await callback.answer()

@router.callback_query(F.data == "ub_connect")
async def process_ub_connect(callback: types.CallbackQuery, state: FSMContext):
    msg = (
        "🔐 **Авторизация UserBot**\n\n"
        "Для работы функций отслеживания мне нужно авторизоваться.\n"
        "Сейчас доступен вход по номеру телефона.\n\n"
        "⚠️ _Ваши данные хранятся только локально на сервере бота._"
    )
    
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Войти по номеру телефона", callback_data="ub_phone_login")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_settings")]
    ])

    await callback.message.edit_text(msg, reply_markup=inline_kb, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "ub_phone_login")
async def process_ub_phone_login(callback: types.CallbackQuery, state: FSMContext):
    msg = (
        "📱 **Вход по номеру телефона**\n\n"
        "Отправьте ваш номер телефона (например: `+79001234567`) или воспользуйтесь кнопкой ниже."
    )
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)],
        [KeyboardButton(text="Отмена")]
    ], resize_keyboard=True)
    
    await callback.message.delete()
    await callback.message.answer(msg, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(UserBotStates.waiting_for_phone)
    await callback.answer()



# Temp storage for users currently logging in: {user_id: Client}
auth_clients = {}

# List of backup proxies (Public MTProto/Socks4/5) - strictly for auth step
PROXY_LIST = [
    {"scheme": "socks5", "hostname": "192.252.208.70", "port": 13915}, # Example public proxy
    {"scheme": "socks5", "hostname": "68.188.156.97", "port": 4145},
]

@router.message(UserBotStates.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Отменено.", reply_markup=get_main_menu())
        await state.clear()
        return

    phone = message.contact.phone_number if message.contact else message.text.strip()
    
    # Use User's Own Keys (REQUIRED for Mobile Session)
    api_id = int(config.API_ID) if config.API_ID else 0
    api_hash = config.API_HASH
    
    status_msg = await message.answer("⏳ **Подключение...**\nПробую разные способы обхода блокировок...")
    
    client = None
    connected = False
    
    # 1. Try Direct IPv4
    try:
        await status_msg.edit_text("⏳ Попытка 1: Прямое подключение...")
        client = Client(
            name=f"auth_{message.from_user.id}", 
            api_id=api_id, 
            api_hash=api_hash, 
            in_memory=True,
            device_model="Samsung SM-S918B",
            system_version="Android 13",
            app_version="9.3.3",
            lang_code="ru"
        )
        await client.connect()
        connected = True
    except Exception as e:
        logging.error(f"IPv4 failed: {e}")

    # 2. Try IPv6 (if IPv4 failed or we want to try generic)
    # 3. Try Proxies
    if not connected:
        for i, proxy in enumerate(PROXY_LIST):
            try:
                await status_msg.edit_text(f"⏳ Попытка {i+2}: Использование прокси...")
                client = Client(
                    name=f"auth_{message.from_user.id}", 
                    api_id=api_id, 
                    api_hash=api_hash, 
                    in_memory=True,
                    proxy=proxy,
                    device_model="Samsung SM-S918B",
                    system_version="Android 13",
                    app_version="9.3.3",
                    lang_code="ru"
                )
                await client.connect()
                connected = True
                break
            except Exception as e:
                 logging.error(f"Proxy {i} failed: {e}")

    if not connected:
         await status_msg.edit_text("❌ **Не удалось подключиться к серверам Telegram.**\nIP-адрес бота временно заблокирован. Попробуйте ввод через Session String.")
         return

    try:
        sent_code = await client.send_code(phone)
        
        auth_clients[message.from_user.id] = {
            "client": client,
            "phone": phone,
            "hash": sent_code.phone_code_hash
        }
        
        await status_msg.edit_text(
            "✅ **Запрос отправлен!**\n\n"
            "Пожалуйста, проверьте личные сообщения от **Telegram** (на телефоне или компьютере).\n"
            "Вы должны получить код подтверждения.\n\n"
            "⌨️ **Введите код сюда** (можно через дефис, например: `1-2-3-4-5`):"
        )
        await state.set_state(UserBotStates.waiting_for_code)
        
    except errors.PhoneNumberInvalid:
        await status_msg.edit_text("❌ Неверный формат номера. Попробуйте еще раз.")
        await client.disconnect()
    except errors.FloodWait as e:
        await status_msg.edit_text(f"❌ Telegram заблокировал вход на {e.value} сек. Попробуйте позже.")
        await client.disconnect()
    except Exception as e:
        logging.error(f"Auth Error: {e}")
        await status_msg.edit_text(f"❌ Ошибка отправки кода: {e}")
        await client.disconnect()





@router.message(UserBotStates.waiting_for_code)
async def process_code(message: types.Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Отменено.", reply_markup=get_main_menu())
        await state.clear()
        if message.from_user.id in auth_clients:
            await auth_clients[message.from_user.id]['client'].disconnect()
            del auth_clients[message.from_user.id]
        return

    code = message.text.replace("-", "").replace(" ", "").strip()
    
    if message.from_user.id not in auth_clients:
        await message.answer("⛔️ Сессия истекла. Начните заново.")
        await state.clear()
        return

    data = auth_clients[message.from_user.id]
    client = data['client']
    phone = data['phone']
    ph_hash = data['hash']
    
    status_msg = await message.answer("⏳ Проверяю код...")
    
    try:
        await client.sign_in(phone, ph_hash, code)
        
        # Success!
        string_session = await client.export_session_string()
        await client.disconnect() # Done with temp client
        del auth_clients[message.from_user.id]
        
        # Save and Start Real Client
        database.save_user_session(message.from_user.id, string_session)
        await ub_manager.start_client(message.from_user.id, string_session)
        
        await status_msg.delete()
        await message.answer("✅ **Успешно!** UserBot подключен и работает.\nТеперь вы будете получать уведомления об удаленных сообщениях в ЛС.", reply_markup=get_main_menu())
        
        # Referral Reward Logic
        referrer_id = database.claim_referral_reward(message.from_user.id)
        if referrer_id:
            try:
                import time
                cur_exp, _ = database.get_user_sub_info(referrer_id)
                base_time = max(time.time(), float(cur_exp or 0))
                new_exp = base_time + (4 * 24 * 3600)
                database.set_subscription(referrer_id, new_exp)
                await bot.send_message(referrer_id, f"🎁 **Бонус за друга!**\n\nВаш друг подключился, вам начислено **4 дня** подписки!")
            except: pass

        await state.clear()

    except errors.SessionPasswordNeeded:
        await status_msg.edit_text(
            "🔐 **Требуется пароль**\n"
            "У вас включена двухэтапная аутентификация.\n"
            "Пожалуйста, введите ваш облачный пароль:"
        )
        await state.set_state(UserBotStates.waiting_for_password)
        
    except errors.PhoneCodeInvalid:
        await status_msg.edit_text("❌ **Неверный код!** Попробуйте еще раз (или напишите 'отмена').")
    except errors.PhoneCodeExpired:
        await status_msg.edit_text("❌ Код устарел. Начните заново.")
        await client.disconnect()
        del auth_clients[message.from_user.id]
        await state.clear()
    except Exception as e:
        logging.error(f"Sign In Error: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {e}")

@router.message(UserBotStates.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Отменено.", reply_markup=get_main_menu())
        await state.clear()
        if message.from_user.id in auth_clients:
            await auth_clients[message.from_user.id]['client'].disconnect()
            del auth_clients[message.from_user.id]
        return

    password = message.text
    # SECURITY: Delete the password message from chat immediately
    try:
        await message.delete()
    except:
        pass
    
    if message.from_user.id not in auth_clients:
        await message.answer("⛔️ Сессия истекла. Начните заново.")
        await state.clear()
        return

    client = auth_clients[message.from_user.id]['client']
    status_msg = await message.answer("⏳ Проверяю пароль...")

    try:
        await client.check_password(password=password)
        
        # Success!
        string_session = await client.export_session_string()
        await client.disconnect()
        del auth_clients[message.from_user.id]
        
        database.save_user_session(message.from_user.id, string_session)
        await ub_manager.start_client(message.from_user.id, string_session)
        
        await status_msg.delete()
        await message.answer("✅ **Авторизация прошла успешно!** UserBot запущен.", reply_markup=get_main_menu())
        await state.clear()
        
    except errors.PasswordHashInvalid:
        await status_msg.edit_text("❌ **Неверный пароль.** Попробуйте еще раз.")
    except Exception as e:
        logging.error(f"2FA Error: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {e}")
