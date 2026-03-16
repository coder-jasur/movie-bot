from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from src.app.api.deps import DbDep
from src.app.database.queries.user import UserActions

app = FastAPI()


class UserIn(BaseModel):
    tg_id: int


@app.post(
    "/user/exists",
    status_code=status.HTTP_200_OK
)
async def check_user(
        user: UserIn,
        db: DbDep
) -> dict:
    async with db.session_factory() as session:
        user_action = UserActions(session)
        user = await user_action.get_user(user.tg_id)

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return {"user_id": user.tg_id}
