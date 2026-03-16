from aiogram.fsm.state import State, StatesGroup

class SearchByGenreSG(StatesGroup):
    select_genres = State()
    results = State()
