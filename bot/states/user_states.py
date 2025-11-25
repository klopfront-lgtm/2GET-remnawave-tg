from aiogram.fsm.state import State, StatesGroup


class UserPromoStates(StatesGroup):
    waiting_for_promo_code = State()


class BalanceTopupStates(StatesGroup):
    waiting_for_custom_amount = State()


class TariffSelectionStates(StatesGroup):
    waiting_for_promo_code = State()
