import asyncpg
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.app.database.queries.user import UserActions
from src.app.keyboards.inline import admin_menu, choose_movie_type, back_to_admin_menu_kbd
from src.app.states.admin.movie import DeleteMovieSG

admin_commands_router = Router()

@admin_commands_router.message(Command("admin_menu"))
async def admin_main_menu(message: Message):
    await message.answer(
        text="выберите действия",
        reply_markup=admin_menu
    )

@admin_commands_router.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu(call: CallbackQuery):
    await call.message.edit_text(
        text="выберите действия",
        reply_markup=admin_menu
    )


@admin_commands_router.callback_query(F.data == "back_to_movie_setup")
async def back_to_admin_menu(call: CallbackQuery):
    await call.message.edit_text(
        text="выберите действия",
        reply_markup=choose_movie_type
    )

@admin_commands_router.callback_query(F.data == "delete_movie")
async def set_up_to_delete_movie(call: CallbackQuery, state: FSMContext):
    await state.set_state(DeleteMovieSG.send_movie_code)
    await call.message.edit_text("отправьте код фильма")

@admin_commands_router.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu(call: CallbackQuery):
    await call.message.edit_text(
        text="выберите действия",
        reply_markup=admin_menu
    )

@admin_commands_router.callback_query(F.data == "users_count")
async def back_to_admin_menu(call: CallbackQuery, pool: asyncpg.Pool):
    try:
        users_actions = UserActions(pool)
        users_data = await users_actions.get_all_user()
        await call.message.edit_text(
            f"количества пользывателей : {len(users_data)}",
            reply_markup=back_to_admin_menu_kbd
        )

    except Exception as e:
        print("ERROR", e)
        await call.message.answer("произошло ошибка")
