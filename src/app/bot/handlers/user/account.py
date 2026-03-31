import logging
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command, or_f
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    SuccessfulPayment,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.common.buttons import BTN_PROFILE, BTN_VIP
from src.app.bot.common.i18n import gettext as _
from src.app.bot.common.i18n import i18n
from src.app.bot.common.i18n import lazy_gettext as __
from src.app.database.queries.user import UserActions

logger = logging.getLogger(__name__)


def get_tashkent_time():
    """Returns current time in Tashkent (UTC+5)."""
    return datetime.utcnow() + timedelta(hours=5)


account_router = Router()


async def smart_edit(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup = None,
    photo: str = None,
):
    """Edits message if possible, correctly handling photos/captions/media.
    Used to prevent TelegramBadRequest when editing invoices or old messages.
    """
    try:
        if message.photo or message.caption:
            if photo:
                # Update photo AND caption/text
                from aiogram.types import InputMediaPhoto

                await message.edit_media(
                    media=InputMediaPhoto(media=photo, caption=text, parse_mode="HTML"),
                    reply_markup=reply_markup,
                )
            else:
                # Only update caption (previous message had a photo)
                await message.edit_caption(
                    caption=text, reply_markup=reply_markup, parse_mode="HTML"
                )
        else:
            # Regular text message
            await message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception as e:
        logger.debug(f"Smart edit failed, falling back to new message: {e}")
        if photo:
            await message.answer_photo(
                photo=photo, caption=text, reply_markup=reply_markup, parse_mode="HTML"
            )
        else:
            await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")


# VIP Prices
VIP_PRICES = {
    "1_day": {"stars": 10, "uzs": 3000, "days": 1, "label": __("1 kunlik VIP")},
    "10_days": {"stars": 60, "uzs": 18000, "days": 10, "label": __("10 kunlik VIP")},
    "30_days": {"stars": 99, "uzs": 29000, "days": 30, "label": __("1 oylik VIP")},
    "90_days": {"stars": 240, "uzs": 69000, "days": 90, "label": __("3 oylik VIP")},
}


@account_router.message(or_f(F.text == BTN_PROFILE, Command("profile", "profil")))
async def profile_handler(message: Message, session: AsyncSession, edit: bool = False):
    from src.app.bot.common.utils import get_user_language

    locale = await get_user_language(message.from_user, session)
    # ✅ i18n kontekstini to'g'ri o'rnatamiz — barcha _() chaqiruvlari shu tildan foydalanadi
    i18n.ctx_locale.set(locale)

    user_actions = UserActions(session)
    user = await user_actions.get_user(message.from_user.id)

    if not user:
        await message.answer(str(_("❌ Ma'lumot topilmadi.")))
        return

    from src.app.bot.common.utils import is_active_vip

    is_vip_active = await is_active_vip(user, session)

    # Check if user is admin for UI label
    from src.app.core.config import load_config

    is_admin = user.tg_id in load_config().admins_ids

    # Auto-cleanup: If flag is active but time is out, update DB
    if user.vip_status == "active" and not is_vip_active and not is_admin:
        await user_actions.update_user(tg_id=user.tg_id, vip_status=None)
        user.vip_status = None
        logger.info(f"VIP status expired for user {user.tg_id}, auto-cleared.")

    vip_status_label = str(_("Faol")) if is_vip_active else str(_("Mavjud emas"))

    # VIP expiry
    expiry_text = ""
    if is_vip_active:
        if is_admin or not user.vip_expires_at:
            expiry_text = f"\n<b>⌛ {str(_('Muddati:'))}</b> {str(_('Cheksiz'))}"
        else:
            expiry_date = user.vip_expires_at.strftime("%d.%m.%Y %H:%M")
            expiry_text = f"\n<b>⌛ {str(_('Muddati:'))}</b> {expiry_date}"

    # Referral
    bot_info = await message.bot.get_me()
    ref_link = f"t.me/{bot_info.username}?start=ref_{user.tg_id}"

    text = (
        f"<b>👤 {_('Profil')}</b>\n\n"
        f"<b>🆔 ID:</b> <code>{user.tg_id}</code>\n"
        f"<b>💎 {_('VIP holati:')}</b> {vip_status_label}{expiry_text}\n\n"
        f"<b>👥 {_('Takliflar:')}</b> {getattr(user, 'joined_count', 0)} {_('ta')}\n"
        f"<b>🔗 {_('Havola:')}</b> {ref_link}"
    )

    # Referral sharing link
    share_text = str(
        _(
            "🍿 Zo'r bot ekan, filmlarni yuqori formatda ko'ryapman! Senga ham tavsiya qilaman:"
        )
    )
    share_url = f"https://t.me/share/url?url={ref_link}&text={share_text}"

    kbd = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🚀 {_('Botni ulashish')}", url=share_url)],
            [
                InlineKeyboardButton(
                    text=f"📅 {_('To\'lovlar tarixi')}",
                    callback_data="payment_history",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"💳 {_('VIP sotib olish')}",
                    callback_data="buy_vip_from_profile",
                )
            ],
        ]
    )

    if locale == "ru":
        file_id = "AgACAgIAAxkBAAICwWnI9rkEQVucoXGjXeDpGWijC69GAAITFWsb_utJSujS1XZlIOrJAQADAgADeAADOgQ"
    elif locale == "en":
        file_id = "AgACAgIAAxkBAAICxWnI9wx28eppVmST9mRIfuQpk6scAAIfFWsb_utJSriYqPdtMqAbAQADAgADeAADOgQ"
    else:
        file_id = "AgACAgIAAxkBAAICsGnI7MzcPYkSPeYnBFnSaUinvbV7AALhFGsb_utJSv1gCeoq-4aMAQADAgADeAADOgQ"

    if edit:
        await smart_edit(message, text, reply_markup=kbd)
    else:
        await message.answer_photo(
            photo=file_id, caption=text, reply_markup=kbd, parse_mode="HTML"
        )


@account_router.callback_query(F.data == "payment_history")
async def payment_history_handler(callback: CallbackQuery, session: AsyncSession):
    user_actions = UserActions(session)
    user = await user_actions.get_user(callback.from_user.id)

    if not user or not user.vip_payment_history:
        await callback.answer(str(_("To'lovlar tarixi bo'sh.")), show_alert=True)
        return

    history = user.vip_payment_history
    if isinstance(history, dict):
        history = [history]

    lines = [f"<b>🕒 {str(_('To\'lovlar tarixi'))}</b>\n"]
    for item in history[-5:]:  # show last 5 for minimalism
        lines.append(
            f"✅ {item.get('date', '??')} | {item.get('amount', '??')} {item.get('currency', '')}"
        )

    kbd = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=str(_("VIP sotib olish")), callback_data="buy_vip_from_profile"
                )
            ]
        ]
    )

    await callback.message.answer("\n".join(lines), reply_markup=kbd, parse_mode="HTML")
    await callback.answer()


@account_router.callback_query(F.data == "buy_vip_from_profile")
async def buy_vip_callback(callback: CallbackQuery, session: AsyncSession):
    await vip_tarif_handler(
        callback.message, session=session, edit=True, user=callback.from_user
    )
    await callback.answer()


@account_router.callback_query(F.data == "back_to_profile")
async def back_to_profile_callback(callback: CallbackQuery, session: AsyncSession):
    await profile_handler(callback.message, session, edit=True)
    await callback.answer()


@account_router.message(or_f(F.text == BTN_VIP, Command("vip")))
async def vip_tarif_handler(
    message: Message,
    session: AsyncSession,
    edit: bool = False,
    user: "User" = None,
):
    from src.app.bot.common.utils import get_user_language

    target_user = user or message.from_user
    locale = await get_user_language(target_user, session)
    # ✅ i18n kontekstini to'g'ri o'rnatamiz
    i18n.ctx_locale.set(locale)
    text = (
        f"<b>⭐ {_('VIP Obuna')}</b>\n\n"
        f"<b>✨ {_('Imkoniyatlar:')}</b>\n"
        f"✅ {_('Yuqori sifat (720p, 1080p)')}\n"
        f"✅ {_('Tillar boshqaruvi')}\n"
        f"✅ {_('Reklamasiz foydalanish')}\n"
        f"✅ {_('Filmlarni yuklab olish')}\n\n"
        f"<b>💰 {_('Narxlar:')}</b>\n"
        f"🎫 {_('1 kun: 3,000 so\'m / 10 Stars')}\n"
        f"🎫 {_('10 kun: 18,000 so\'m / 60 Stars')}\n"
        f"🎫 {_('30 kun: 29,000 so\'m / 99 Stars')}\n"
        f"🎫 {_('90 kun: 69,000 so\'m / 240 Stars')}\n\n"
        f"🎁 <i>{_('5 ta do\'stingizni taklif qiling va 3 kunlik VIP bepul oling!')}</i>"
    )

    kbd = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=str(_("1 kun")), callback_data="select_plan:1_day"
                )
            ],
            [
                InlineKeyboardButton(
                    text=str(_("10 kun")), callback_data="select_plan:10_days"
                )
            ],
            [
                InlineKeyboardButton(
                    text=str(_("30 kun")), callback_data="select_plan:30_days"
                )
            ],
            [
                InlineKeyboardButton(
                    text=str(_("3 oy (90 kun)")), callback_data="select_plan:90_days"
                )
            ],
        ]
    )
    if locale == "ru":
        file_id = "AgACAgIAAxkBAAICwWnI9rkEQVucoXGjXeDpGWijC69GAAITFWsb_utJSujS1XZlIOrJAQADAgADeAADOgQ"
    elif locale == "en":
        file_id = "AgACAgIAAxkBAAICxWnI9wx28eppVmST9mRIfuQpk6scAAIfFWsb_utJSriYqPdtMqAbAQADAgADeAADOgQ"
    else:
        file_id = "AgACAgIAAxkBAAICsGnI7MzcPYkSPeYnBFnSaUinvbV7AALhFGsb_utJSv1gCeoq-4aMAQADAgADeAADOgQ"

    if edit:
        await smart_edit(message, text, reply_markup=kbd, photo=file_id)
    else:
        await message.answer_photo(
            photo=file_id, caption=text, reply_markup=kbd, parse_mode="HTML"
        )

@account_router.callback_query(F.data.startswith("select_plan:"))
async def select_payment_method_handler(callback: CallbackQuery, session: AsyncSession):
    plan_key = callback.data.split(":")[1]
    plan = VIP_PRICES.get(plan_key)

    if not plan:
        await callback.answer(str(_("Xatolik.")))
        return

    text = (
        f"<b>💳 {_('To\'lov usuli')}</b>\n\n"
        f"🎫 {str(plan['label'])}\n"
        f"🔹 {_('Admin orqali:')} {plan['uzs']:,} {_('so\'m')}\n"
        f"🔹 {_('Stars:')} {plan['stars']} Stars"
    )

    kbd = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=str(_("Stars (XTR)")), callback_data=f"pay:{plan_key}:stars"
                )
            ],
            [
                InlineKeyboardButton(
                    text=str(_("Admin orqali")), callback_data=f"pay:{plan_key}:admin"
                )
            ],
            [
                InlineKeyboardButton(
                    text=str(_("Orqaga")), callback_data="buy_vip_from_profile"
                )
            ],
        ]
    )

    from src.app.bot.common.utils import get_user_language

    # Now correctly passing session to get the user's DB language preference
    locale = await get_user_language(callback.from_user, session=session)

    if locale == "ru":
        banner_file_id = "AgACAgIAAxkBAAICwWnI9rkEQVucoXGjXeDpGWijC69GAAITFWsb_utJSujS1XZlIOrJAQADAgADeAADOgQ"
    elif locale == "en":
        banner_file_id = "AgACAgIAAxkBAAICxWnI9wx28eppVmST9mRIfuQpk6scAAIfFWsb_utJSriYqPdtMqAbAQADAgADeAADOgQ"
    else:
        banner_file_id = "AgACAgIAAxkBAAICsGnI7MzcPYkSPeYnBFnSaUinvbV7AALhFGsb_utJSv1gCeoq-4aMAQADAgADeAADOgQ"

    await smart_edit(callback.message, text, reply_markup=kbd, photo=banner_file_id)
    await callback.answer()


@account_router.callback_query(F.data.startswith("pay:") & F.data.endswith(":admin"))
async def admin_payment_handler(callback: CallbackQuery):
    from src.app.core.config import load_config

    settings = load_config()

    parts = callback.data.split(":")
    plan_key = parts[1]
    plan = VIP_PRICES.get(plan_key)
    if not plan:
        await callback.answer(str(_("Xatolik.")))
        return

    text = (
        f"{_('Admin orqali to\'lov')}\n\n"
        f"🎫 {str(plan['label'])}\n"
        f"💰 {_('Narx:')} {plan['uzs']:,} {_('so\'m')}\n"
        f"💳 {_('Karta raqami:')} <code>{settings.payment_card}</code>\n\n"
        f"{_('Iltimos, ushbu karta raqamiga pul o\'tkazing va to\'lov rasmini (skrinshot) @hikmatilloyev_J adminga yuboring.')}"
    )

    kbd = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=str(_("⬅️ Orqaga")), callback_data=f"select_plan:{plan_key}"
                )
            ]
        ]
    )

    await smart_edit(callback.message, text, reply_markup=kbd)
    await callback.answer()


@account_router.callback_query(F.data.startswith("pay:"))
async def send_invoice_handler(callback: CallbackQuery, settings: "Settings" = None):
    # settings is passed via DP workflow data or manually if not working
    if not settings:
        from src.app.core.config import load_config

        settings = load_config()

    parts = callback.data.split(":")
    plan_key = parts[1]
    method = parts[2]
    plan = VIP_PRICES.get(plan_key)

    if not plan:
        await callback.answer(str(_("❌ Tarif topilmadi.")))
        return

    provider_token = None
    currency = "UZS"
    is_test = False
    prices = []

    if method == "stars":
        prices = [LabeledPrice(label=str(plan["label"]), amount=plan["stars"])]
        currency = "XTR"
        provider_token = None  # For Stars it must be None or omitted
        is_test = False  # Stars real
    elif method == "click":
        token = settings.click_provider_token
        if not token or "YOUR_CLICK_TOKEN" in token:
            await callback.answer(
                str(_("❌ Xatolik yuzaga keldi. Iltimos, keyinroq urinib ko'ring.")),
                show_alert=True,
            )
            return

        # Prices in minor units (UZS * 100)
        prices = [LabeledPrice(label=str(plan["label"]), amount=plan["uzs"] * 100)]
        currency = "UZS"
        provider_token = token
        is_test = False  # Click real

    elif method == "payme":
        token = settings.payme_provider_token
        if not token or "YOUR_PAYME_TOKEN" in token:
            await callback.answer(
                str(_("❌ Xatolik yuzaga keldi. Iltimos, keyinroq urinib ko'ring.")),
                show_alert=True,
            )
            return

        # Prices in minor units (UZS * 100)
        prices = [LabeledPrice(label=str(plan["label"]), amount=plan["uzs"] * 100)]
        currency = "UZS"
        provider_token = token
        is_test = False  # Payme real

    try:
        # Create localized pay button to avoid default Telegram Russian button
        kbd = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=(
                            str(_("To'lash {amount} UZS")).format(
                                amount=f"{plan['uzs']:,}".replace(",", " "),
                            )
                            if method != "stars"
                            else str(_("To'lash {amount} Stars")).format(
                                amount=plan["stars"]
                            )
                        ),
                        pay=True,
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=str(_("⬅️ Orqaga")), callback_data=f"select_plan:{plan_key}"
                    )
                ],
            ]
        )

        await callback.message.answer_invoice(
            title=str(plan["label"]),
            description=str(_("{days} kunlik VIP obuna uchun to'lov")).format(
                days=plan["days"]
            ),
            prices=prices,
            payload=f"{plan_key}:{method}",
            provider_token=provider_token,
            currency=currency,
            start_parameter="vip_purchase",
            is_test=is_test,
            reply_markup=kbd,
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error sending invoice: {e}")
        error_msg = str(e)
        if "PAYMENT_PROVIDER_INVALID" in error_msg:
            await callback.answer(
                str(
                    _(
                        "❌ To'lov provayderi tokeni noto'g'ri. BotFather'dan olingan tokenni tekshiring."
                    )
                ),
                show_alert=True,
            )
        else:
            await callback.answer(
                str(_("❌ Hisob-faktura yuborishda xatolik yuz berdi: {error}")).format(
                    error=error_msg[:50]
                ),
                show_alert=True,
            )


@account_router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@account_router.message(F.successful_payment)
async def successful_payment_handler(message: Message, session: AsyncSession):
    payment: SuccessfulPayment = message.successful_payment
    payload = payment.invoice_payload.split(":")
    plan_key = payload[0]
    method = payload[1]
    plan = VIP_PRICES.get(plan_key)

    if not plan:
        logger.error(f"Unknown plan {plan_key} in successful payment")
        return

    user_actions = UserActions(session)
    user = await user_actions.get_user(message.from_user.id)

    # Calculate new expiry date
    now = get_tashkent_time()
    current_expiry = (
        user.vip_expires_at
        if user and user.vip_expires_at and user.vip_expires_at > now
        else now
    )
    new_expiry = current_expiry + timedelta(days=plan["days"])

    # Update payment history
    history = user.vip_payment_history or []
    if isinstance(history, dict):
        history = [history]

    amount = plan["stars"] if method == "stars" else plan["uzs"]
    currency_label = "Stars" if method == "stars" else "UZS"

    history.append(
        {
            "date": now.strftime("%d.%m.%Y %H:%M"),
            "amount": amount,
            "currency": currency_label,
            "label": str(plan["label"]),
            "status": "success",
        }
    )

    await user_actions.update_user(
        tg_id=message.from_user.id,
        vip_status="active",
        vip_expires_at=new_expiry,
        vip_payment_history=history,
    )

    await message.answer(
        f"<b>{str(_('To\'lov muvaffaqiyatli!'))}</b>\n\n"
        f"{str(_('VIP:'))} {plan['days']} {str(_('kun'))}\n"
        f"{str(_('Muddati:'))} {new_expiry.strftime('%d.%m.%Y')}",
        parse_mode="HTML",
    )
