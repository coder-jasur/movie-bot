import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.common.i18n import gettext as _
from src.app.bot.common.i18n import i18n
from src.app.bot.keyboards.replay import get_main_menu
from src.app.bot.settings.bot_commands import set_user_commands
from src.app.core.config import Settings
from src.app.database.queries.admin import AdminActions
from src.app.database.queries.referral import ReferralActions
from src.app.database.queries.user import UserActions

start_router = Router()
logger = logging.getLogger(__name__)


@start_router.message(CommandStart())
async def start_bot(
    message: Message, command: CommandStart, session: AsyncSession, settings: Settings
):
    user_actions = UserActions(session)
    referral_actions = ReferralActions(session)
    args = command.args

    # Получение данных пользователя
    user_data = await user_actions.get_user(message.from_user.id)

    # Agar foydalanuvchi yo'q bo'lsa — qo'shamiz (Lekin tilini None qilamiz, majburiy tanlash uchun)
    if not user_data:
        await user_actions.add_user(
            tg_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            language_code=None,  # Majburiy til tanlash uchun None
            is_premium=message.from_user.is_premium or False,
        )

        # Refferal tekshirish
        if args and args.startswith("ref_"):
            try:
                referral_id = int(args.split("_")[1])
                logger.info(f"Referral link clicked: referral_id={referral_id}, new_user={message.from_user.id}")

                # 1. Avval admin Referral jadvalidan tekshiramiz
                referral_actions = ReferralActions(session)
                admin_referral = await referral_actions.get_referral(referral_id)

                if admin_referral:
                    # ✅ Admin tomonidan yaratilgan referral
                    await referral_actions.increment_joined_count(referral_id)
                    logger.info(f"Admin referral incremented: referral_id={referral_id}, new_count={admin_referral.joined_count + 1}")
                else:
                    # 2. Foydalanuvchi o'zining tg_id si bo'yicha referral yuborgan
                    new_count = await user_actions.increment_joined_count(referral_id)
                    logger.info(f"User referral incremented: tg_id={referral_id}, new_count={new_count}")

                    # Reward: 3 days for every 5 referrals
                    if new_count is not None and new_count >= 5:
                        referrer = await user_actions.get_user(referral_id)
                        if referrer:
                            from datetime import timedelta
                            from src.app.bot.handlers.user.account import get_tashkent_time

                            now = get_tashkent_time()
                            current_expiry = (
                                referrer.vip_expires_at
                                if referrer.vip_expires_at and referrer.vip_expires_at > now
                                else now
                            )
                            new_expiry = current_expiry + timedelta(days=3)

                            await user_actions.update_user(
                                tg_id=referral_id,
                                vip_status="active",
                                vip_expires_at=new_expiry,
                                joined_count=0,  # Reset count
                            )

                            # Notify the referrer
                            try:
                                invite_msg = _(
                                    "<b>🎁 Tabriklaymiz!</b>\n\n"
                                    "Siz 5 ta do'stingizni taklif qildingiz va <b>3 kunlik VIP</b> statusiga ega bo'ldingiz! 🍿"
                                )
                                await message.bot.send_message(
                                    chat_id=referral_id,
                                    text=str(invite_msg),
                                    parse_mode="HTML",
                                )
                            except Exception as e:
                                logger.error(f"Failed to notify referrer {referral_id}: {e}")

            except (ValueError, IndexError) as e:
                logger.warning(f"Referral parse error for args={args!r}: {e}")
            except Exception as e:
                logger.error(f"Referral processing error for args={args!r}: {e}", exc_info=True)


        # user_data yangilash
        user_data = await user_actions.get_user(message.from_user.id)

    if args and args.isdigit():
        from src.app.bot.handlers.user.movie_search import movie_search_handler

        msg_copy = message.model_copy(update={"text": args})
        await movie_search_handler(msg_copy, session)
        return

    # Определение имени пользователя
    name = (
        message.from_user.first_name
        or message.from_user.last_name
        or message.from_user.full_name
        or str(_("Do'stim"))
    )

    # Agar foydalanuvchining tili belgilanmagan bo'lsa
    if not user_data or not user_data.language_code:
        from src.app.bot.keyboards.inline import get_language_inline_markup

        await message.answer(
            _(
                "🇺🇿 Iltimos, tilni tanlang:\n"
                "🇷🇺 Пожалуйста, выберите язык:\n"
                "🇺🇸 Please select a language:"
            ),
            reply_markup=get_language_inline_markup(),
        )
        return

    # O'zgaruvchilarni yangilash (agar oldin bo'lsa)
    user_data = await user_actions.get_user(message.from_user.id)
    language_code = user_data.language_code if user_data else "uz"

    # i18n kontekstini sozlash
    i18n.ctx_locale.set(language_code)

    # Update bot commands for this user based on their DB language and admin status
    admin_actions = AdminActions(session)
    is_admin = (message.from_user.id in settings.admins_ids) or (
        await admin_actions.is_admin(message.from_user.id)
    )

    await set_user_commands(
        message.bot, message.from_user.id, language_code, is_admin=is_admin
    )

    await message.answer(
        _(
            "<b>👋 Salom {name}</b>\n\n"
            "<b>Botimizga xush kelibsiz.</b>\n\n"
            "<b>🍿 Kino kodini yuboring:</b>"
        ).format(name=name),
        reply_markup=get_main_menu(),
    )
