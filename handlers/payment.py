import logging
import datetime
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
import config
import database
from loader import bot
from states import PromoStates

router = Router()

# Prices
PRICE_7_DAYS_XTR = 35
PRICE_30_DAYS_XTR = 100
PRICE_7_DAYS_RUB = 60
PRICE_30_DAYS_RUB = 180

@router.message(F.text == "👤 Профиль / Подписка")
@router.message(Command("profile"))
async def cmd_profile(message: types.Message, user_id: int = None):
    if not user_id:
        user_id = message.from_user.id
    expiry_str, trial_used = database.get_user_sub_info(user_id)
    
    is_active = False
    expiry_date = None
    
    import time
    from datetime import datetime
    
    if expiry_str:
        try:
            # Robust conversion
            try:
                ts = float(expiry_str)
            except (ValueError, TypeError):
                dt = datetime.fromisoformat(str(expiry_str))
                ts = dt.timestamp()
            
            if ts > time.time():
                is_active = True
                expiry_date = datetime.fromtimestamp(ts)
        except Exception as e:
            logging.error(f"Date parsing error in profile: {e}")

    status_text = "✅ Активна" if is_active else "❌ Не активна"
    expiry_text = expiry_date.strftime("%d.%m.%Y %H:%M") if is_active else "—"
    
    total_refs, active_refs = database.get_referral_stats(user_id)
    
    msg = (
        f"👤 **Профиль пользователя**\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"💎 Подписка: **{status_text}**\n"
        f"📅 Истекает: `{expiry_text}`\n\n"
        f"👥 **Рефералы:** {total_refs} (Активных: {active_refs})\n"
        f"🎁 *Пригласи друга и получи 4 дня бесплатно!*\n\n"
        "💳 **Тарифы:**\n"
        f"▫️ 7 дней: {PRICE_7_DAYS_XTR} ⭐️ или {PRICE_7_DAYS_RUB} ₽\n"
        f"▫️ 30 дней: {PRICE_30_DAYS_XTR} ⭐️ или {PRICE_30_DAYS_RUB} ₽"
    )
    
    kb_rows = []
    
    if not is_active:
        if not trial_used:
            kb_rows.append([InlineKeyboardButton(text="🎁 Активировать пробный период (3 дня)", callback_data="activate_trial")])
        
        kb_rows.append([InlineKeyboardButton(text=f"💳 Купить на 7 дней", callback_data="select_7")])
        kb_rows.append([InlineKeyboardButton(text=f"💳 Купить на 30 дней", callback_data="select_30")])
    else:
        kb_rows.append([InlineKeyboardButton(text="➕ Продлить подписку", callback_data="extend_sub")])

    kb_rows.append([InlineKeyboardButton(text="🔗 Получить ссылку", callback_data="get_ref_link")])
    kb_rows.append([InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="enter_promo")])

    await message.answer(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows), parse_mode="Markdown")

@router.callback_query(F.data == "activate_trial")
async def process_activate_trial(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    expiry_str, trial_used = database.get_user_sub_info(user_id)
    
    if trial_used:
        await callback.answer("❌ Вы уже использовали пробный период!", show_alert=True)
        return

    # Add 3 days
    import time
    new_expiry_ts = time.time() + (3 * 24 * 3600)
    database.set_subscription(user_id, new_expiry_ts, trial_used=True)
    
    from datetime import datetime
    expiry_date = datetime.fromtimestamp(new_expiry_ts)
    
    await callback.message.edit_text(
        "✅ **Пробный период активирован!**\n\n"
        "Теперь у вас есть 3 дня полного доступа к функциям UserBot.\n"
        f"Истекает: `{expiry_date.strftime('%d.%m.%Y %H:%M')}`"
    )
    await callback.answer()

@router.callback_query(F.data.in_({"extend_sub"}))
async def show_payment_options(callback: types.CallbackQuery):
    kb_rows = [
        [InlineKeyboardButton(text="💳 Продлить на 7 дней", callback_data="select_7")],
        [InlineKeyboardButton(text="💳 Продлить на 30 дней", callback_data="select_30")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_profile")]
    ]
    await callback.message.edit_text("Выберите тариф для продления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))

@router.callback_query(F.data.startswith("select_"))
async def process_select_method(callback: types.CallbackQuery):
    days = callback.data.split("_")[1]
    xtr_price = PRICE_7_DAYS_XTR if days == "7" else PRICE_30_DAYS_XTR
    rub_price = PRICE_7_DAYS_RUB if days == "7" else PRICE_30_DAYS_RUB
    
    kb_rows = [
        [InlineKeyboardButton(text=f"⭐️ Telegram Stars ({xtr_price})", callback_data=f"pay_{days}_XTR")],
        [InlineKeyboardButton(text=f"💳 Карта / СБП / SberPay ({rub_price} ₽)", callback_data=f"pay_{days}_RUB")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_profile")]
    ]
    await callback.message.edit_text(f"Выберите способ оплаты для {days} дней:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))

@router.callback_query(F.data.startswith("pay_"))
async def process_pay(callback: types.CallbackQuery):
    _, days, method = callback.data.split("_")
    
    if method == "XTR":
        price_val = PRICE_7_DAYS_XTR if days == "7" else PRICE_30_DAYS_XTR
        currency = "XTR"
        provider_token = ""
        amount = price_val # Stars are integers
    else:
        price_val = PRICE_7_DAYS_RUB if days == "7" else PRICE_30_DAYS_RUB
        currency = "RUB"
        provider_token = config.PAYMENT_TOKEN
        amount = int(price_val * 100) # RUB is in kopeks
        
        if not provider_token:
            await callback.answer("❌ Оплата картой временно недоступна (не настроен PAYMENT_TOKEN)", show_alert=True)
            return

    title = f"Подписка ({days} дней)"
    payload = f"sub_{days}_days"
    prices = [LabeledPrice(label=title, amount=amount)]
    
    provider_data = None
    if method == "RUB":
        import json
        # receipt for YooKassa (Self-employed/IP requirements)
        provider_data = json.dumps({
            "receipt": {
                "items": [
                    {
                        "description": title,
                        "quantity": "1.00",
                        "amount": {
                            "value": f"{price_val}.00",
                            "currency": "RUB"
                        },
                        "vat_code": 1 # 1 = No VAT (standard for self-employed/IP on special tax)
                    }
                ]
            }
        })

    import asyncio
    invoice_msg = await callback.message.answer_invoice(
        title=title,
        description="Доступ к отслеживанию удаленных сообщений.",
        payload=payload,
        provider_token=provider_token,
        currency=currency,
        prices=prices,
        start_parameter="pay_sub",
        provider_data=provider_data,
        need_email=(method == "RUB"),
        send_email_to_provider=(method == "RUB"),
        need_phone_number=(method == "RUB"),
        send_phone_number_to_provider=(method == "RUB")
    )
    await callback.answer()
    
    # Auto-delete invoice after 5 minutes
    async def delete_later(msg: types.Message):
        await asyncio.sleep(300) # 5 minutes
        try:
            await msg.delete()
        except: pass
    asyncio.create_task(delete_later(invoice_msg))

@router.callback_query(F.data == "get_ref_link")
async def show_ref_link(callback: types.CallbackQuery):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{callback.from_user.id}"
    
    text = (
        "🔗 **Ваша реферальная ссылка:**\n\n"
        f"`{ref_link}`\n\n"
        "🎁 **Условия:**\n"
        "За каждого приглашенного друга, который нажмет кнопку старт и **подключит UserBot**, вы получите **4 дня подписки** бесплатно!"
    )
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_profile")]]), parse_mode="Markdown")
    await callback.answer()

@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@router.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    
    days = 0
    if payload == "sub_7_days": days = 7
    elif payload == "sub_30_days": days = 30
    
    import time
    from datetime import datetime
    
    # Calculate new expiry
    current_expiry_str, _ = database.get_user_sub_info(user_id)
    base_time = time.time()
    
    if current_expiry_str:
        try:
            ts = float(current_expiry_str)
            if ts > base_time:
                base_time = ts
        except:
            pass
            
    new_expiry_ts = base_time + (days * 24 * 3600)
    database.set_subscription(user_id, new_expiry_ts)
    
    expiry_date = datetime.fromtimestamp(new_expiry_ts)
    await message.answer(
        f"🎉 **Оплата прошла успешно!**\n\n"
        f"Ваша подписка продлена на {days} дней.\n"
        f"📅 Новая дата окончания: `{expiry_date.strftime('%d.%m.%Y %H:%M')}`"
    )

@router.callback_query(F.data == "enter_promo")
async def process_enter_promo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎟 **Введите ваш промокод:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_profile")]]))
    from states import PromoStates
    await state.set_state(PromoStates.waiting_for_promo)
    await callback.answer()

@router.message(PromoStates.waiting_for_promo)
async def handle_promo_input(message: types.Message, state: FSMContext):
    promo_code = message.text.strip()
    days = database.use_promo_code(promo_code)
    
    if days:
        import time
        from datetime import datetime
        user_id = message.from_user.id
        current_expiry_str, _ = database.get_user_sub_info(user_id)
        base_time = time.time()
        
        if current_expiry_str:
            try:
                ts = float(current_expiry_str)
                if ts > base_time:
                    base_time = ts
            except: pass
            
        new_expiry_ts = base_time + (days * 24 * 3600)
        database.set_subscription(user_id, new_expiry_ts)
        
        expiry_date = datetime.fromtimestamp(new_expiry_ts)
        await message.answer(f"✅ **Промокод активирован!**\n\nВы получили {days} дней подписки.\n📅 Истекает: `{expiry_date.strftime('%d.%m.%Y %H:%M')}`", parse_mode="Markdown")
        await state.clear()
        await cmd_profile(message, user_id=user_id)
    else:
        await message.answer("❌ **Неверный или уже использованный промокод!**", parse_mode="Markdown")

@router.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    try:
        await callback.message.delete()
    except: pass
    await cmd_profile(callback.message, user_id=user_id)
