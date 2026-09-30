from aiogram.fsm.state import State, StatesGroup


class AIChatState(StatesGroup):
    waiting_for_question = State()

class PaymentFlow(StatesGroup):
    waiting_for_receipt = State()


class AdminMode(StatesGroup):
    uploading = State()
    editing_title = State()
    waiting_for_course_code = State()
    waiting_for_course_name = State()
    editing_course_name = State()
    editing_course_code = State()
    waiting_for_intro_video = State()
    waiting_for_payment_setting = State()
