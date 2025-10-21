from aiogram.fsm.state import StatesGroup, State

class ChannelsMenu(StatesGroup):
    menu = State()

class AddChannelSG(StatesGroup):
    get_channel_data = State()
    get_channel_link = State()


class ChannelMenu(StatesGroup):
    menu = State()
    delite_channel = State()
