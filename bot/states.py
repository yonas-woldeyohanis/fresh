from aiogram.fsm.state import State, StatesGroup


class PaymentFlow(StatesGroup):
    waiting_for_receipt = State()


class AdminMode(StatesGroup):
    uploading = State()
    editing_title = State()
