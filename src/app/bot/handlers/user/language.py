from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.database.queries.user import UserActions
from src.app.database.queries.admin import AdminActions
from src.app.bot.keyboards.replay import get_main_menu
from src.app.bot.keyboards.inline import get_language_inline_markup
from src.app.bot.keyboards.callback_data import LanguageCD
from src.app.bot.common.i18n import i18n, gettext as _
from src.app.bot.settings.bot_commands import set_user_commands
from src.app.core.config import Settings

language_router = Router()


@language_router.message(Command("language"))
async def language_command(message: Message):
    await message.answer(
        "🇺🇿 Iltimos, tilni tanlang:\n"
        "🇷🇺 Пожалуйста, выберите язык:\n"
        "🇺🇸 Please select a language:",
        reply_markup=get_language_inline_markup()
    )


@language_router.callback_query(LanguageCD.filter())
async def set_language_callback(
    callback: CallbackQuery,
    callback_data: LanguageCD,
    session: AsyncSession,
    settings: Settings
):
    user_actions = UserActions(session)
    lang_code = callback_data.code

    await user_actions.update_user(callback.from_user.id, language_code=lang_code)

    # Locale kontekstini yangilash
    i18n.ctx_locale.set(lang_code)

    # Foydalanuvchi uchun bot komandalarini yangilash
    admin_actions = AdminActions(session)
    is_admin = (
        callback.from_user.id in settings.admins_ids
    ) or (
        await admin_actions.is_admin(callback.from_user.id)
    )
    await set_user_commands(callback.bot, callback.from_user.id, lang_code, is_admin=is_admin)

    name = (
        callback.from_user.first_name
        or callback.from_user.last_name
        or callback.from_user.full_name
        or _("Do'stim")
    )

    await callback.message.delete()

    await callback.message.answer(
        _(
            "<b>👋 Salom {name}</b>\n"
            "\n"
            "<b>Botimizga xush kelibsiz.</b>\n"
            "\n"
            "<b>🍿 Kino kodini yuboring:</b>"
        ).format(name=name),
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    await callback.answer()