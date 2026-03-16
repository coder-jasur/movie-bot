from aiogram.fsm.state import State, StatesGroup

class ReferralSG(StatesGroup):
    menu = State()
    add = State()
    view = State()
