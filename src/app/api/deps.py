from typing import Annotated

from fastapi.params import Depends

from src.app.core.config import Settings, load_config
from src.app.database.core import Database

settings = load_config()
database = Database(settings.construct_postgresql_url())

async def get_db() -> Database:
    return database


DbDep = Annotated[Database, Depends(get_db)]
