from aiogram.fsm.state import State, StatesGroup

class Form(StatesGroup):
    waiting_for_broadcast = State()

class UserBotStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_password = State()

class SettingsStates(StatesGroup):
    waiting_for_city = State()
    waiting_for_category = State()

class PromoStates(StatesGroup):
    waiting_for_promo = State()
