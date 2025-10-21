from aiogram.fsm.state import StatesGroup, State


class AdminStateSG(StatesGroup):
    menu = State()

class BroadcastingManagerSG(StatesGroup):
    get_message = State()
    confirm_broadcasting = State()
