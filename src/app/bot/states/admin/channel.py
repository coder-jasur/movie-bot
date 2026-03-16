from aiogram.fsm.state import StatesGroup, State

class OPMenu(StatesGroup):
    menu = State()

class AddChannelState(StatesGroup):
    get_channel_data = State()
    get_channel_link = State()

class AddBotState(StatesGroup):
    get_bot_name = State()
    get_bot_username = State()
    get_bot_link = State()

class BotMenu(StatesGroup):
    menu = State()
    delete_bot = State()


class ChannelMenu(StatesGroup):
    menu = State()
    delete_channel = State()
