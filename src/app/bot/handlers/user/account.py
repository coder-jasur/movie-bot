from aiogram import Router, F, Bot
from aiogram.filters import Command, or_f
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, LabeledPrice, PreCheckoutQuery, SuccessfulPayment
)
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from datetime import datetime, timedelta

from src.app.bot.common.buttons import BTN_VIP, BTN_PROFILE
from src.app.bot.common.i18n import i18n, gettext as _, lazy_gettext as __
from src.app.database.queries.user import UserActions

logger = logging.getLogger(__name__)

def get_tashkent_time():
    """Returns current time in Tashkent (UTC+5)."""
    return datetime.utcnow() + timedelta(hours=5)

account_router = Router()

# VIP Prices
VIP_PRICES = {
    "1_day": {
        "stars": 10,
        "uzs": 3000,
        "days": 1,
        "label": __("1 kunlik VIP")
    },
    "10_days": {
        "stars": 50,
        "uzs": 15000,
        "days": 10,
        "label": __("10 kunlik VIP")
    },
    "30_days": {
        "stars": 85,
        "uzs": 25000,
        "days": 30,
        "label": __("1 oylik VIP")
    },
}

@account_router.message(or_f(F.text == BTN_PROFILE, Command("profile", "profil")))
async def profile_handler(message: Message, session: AsyncSession):
    user_actions = UserActions(session)
    user = await user_actions.get_user(message.from_user.id)
    
    if not user:
        await message.answer(str(_("❌ Ma'lumot topilmadi.")))
        return

    vip_status = str(_("Faol")) if user.vip_status == "active" else str(_("Mavjud emas"))
    
    # VIP expiry
    expiry_text = ""
    if user.vip_status == "active":
        if user.vip_expires_at:
            expiry_date = user.vip_expires_at.strftime('%d.%m.%Y %H:%M')
            expiry_text = f"\n<b>⌛ {str(_('Muddati:'))}</b> {expiry_date}"
        else:
            expiry_text = f"\n<b>⌛ {str(_('Muddati:'))}</b> {str(_('Cheksiz'))}"
    
    # Referral
    bot_info = await message.bot.get_me()
    ref_link = f"t.me/{bot_info.username}?start=ref_{user.tg_id}"

    text = (
        f"<b>👤 {str(_('Profil'))}</b>\n\n"
        f"<b>🆔 ID:</b> <code>{user.tg_id}</code>\n"
        f"<b>💎 {str(_('VIP holati:'))}</b> {vip_status}{expiry_text}\n\n"
        f"<b>👥 {str(_('Takliflar:'))}</b> {getattr(user, 'joined_count', 0)} {str(_('ta'))}\n"
        f"<b>🔗 {str(_('Havola:'))}</b> {ref_link}"
    )
    
    # Referral sharing link
    share_text = str(_("🍿 Zo'r bot ekan, filmlarni yuqori formatda ko'ryapman! Senga ham tavsiya qilaman:"))
    share_url = f"https://t.me/share/url?url={ref_link}&text={share_text}"

    kbd = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🚀 {str(_('Botni ulashish'))}", url=share_url)],
        [InlineKeyboardButton(text=f"📅 {str(_('To\'lovlar tarixi'))}", callback_data="payment_history")],
        [InlineKeyboardButton(text=f"💳 {str(_('VIP sotib olish'))}", callback_data="buy_vip_from_profile")]
    ])
    
    await message.answer(text, reply_markup=kbd, parse_mode="HTML")

@account_router.callback_query(F.data == "payment_history")
async def payment_history_handler(callback: CallbackQuery, session: AsyncSession):
    user_actions = UserActions(session)
    user = await user_actions.get_user(callback.from_user.id)
    
    if not user or not user.vip_payment_history:
        await callback.answer(str(_("To'lovlar tarixi bo'sh.")), show_alert=True)
        return

    history = user.vip_payment_history
    if isinstance(history, dict): history = [history]
        
    lines = [f"<b>🕒 {str(_('To\'lovlar tarixi'))}</b>\n"]
    for item in history[-5:]: # show last 5 for minimalism
        lines.append(f"✅ {item.get('date', '??')} | {item.get('amount', '??')} {item.get('currency', '')}")
        
    kbd = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(_("VIP sotib olish")), callback_data="buy_vip_from_profile")]
    ])
        
    await callback.message.answer("\n".join(lines), reply_markup=kbd, parse_mode="HTML")
    await callback.answer()

@account_router.callback_query(F.data == "buy_vip_from_profile")
async def buy_vip_callback(callback: CallbackQuery):
    await vip_tarif_handler(callback.message)
    await callback.answer()

@account_router.callback_query(F.data == "back_to_profile")
async def back_to_profile_callback(callback: CallbackQuery, session: AsyncSession):
    await profile_handler(callback.message, session)
    await callback.message.delete()
    await callback.answer()

@account_router.message(or_f(F.text == BTN_VIP, Command("vip")))
async def vip_tarif_handler(message: Message):
    text = (
        f"<b>⭐ {str(_('VIP Obuna'))}</b>\n\n"
        f"<b>✨ {str(_('Imkoniyatlar:'))}</b>\n"
        f"✅ {str(_('Yuqori sifat (720p, 1080p)'))}\n"
        f"✅ {str(_('Reklamasiz foydalanish'))}\n"
        f"✅ {str(_('Filmlarni yuklab olish'))}\n\n"
        f"<b>💰 {str(_('Narxlar:'))}</b>\n"
        f"🎫 {str(_('1 kun: 3,000 so\'m / 10 Stars'))}\n"
        f"🎫 {str(_('10 kun: 15,000 so\'m / 50 Stars'))}\n"
        f"🎫 {str(_('30 kun: 25,000 so\'m / 85 Stars'))}\n\n"
        f"🎁 <i>{str(_('5 ta do\'stingizni taklif qiling va 3 kunlik VIP bepul oling!'))}</i>"
    )
    
    kbd = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(_("1 kun")), callback_data="select_plan:1_day")],
        [InlineKeyboardButton(text=str(_("10 kun")), callback_data="select_plan:10_days")],
        [InlineKeyboardButton(text=str(_("30 kun")), callback_data="select_plan:30_days")],
        [InlineKeyboardButton(text=str(_("⬅️ Orqaga")), callback_data="back_to_profile")]
    ])
    
    await message.answer(text, reply_markup=kbd, parse_mode="HTML")

@account_router.callback_query(F.data.startswith("select_plan:"))
async def select_payment_method_handler(callback: CallbackQuery):
    plan_key = callback.data.split(":")[1]
    plan = VIP_PRICES.get(plan_key)
    
    if not plan:
        await callback.answer(str(_("Xatolik.")))
        return

    text = (
        f"<b>💳 {str(_('To\'lov usuli'))}</b>\n\n"
        f"🎫 {str(plan['label'])}\n"
        f"🔹 {str(_('Click (Humo, Uzcard):'))} {plan['uzs']} {str(_('so\'m'))}\n"
        f"🔹 {str(_('Stars:'))} {plan['stars']} Stars"
    )

    kbd = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(_("Click (Humo, Uzcard)")), callback_data=f"pay:{plan_key}:click")],
        [InlineKeyboardButton(text=str(_("Stars (XTR)")), callback_data=f"pay:{plan_key}:stars")],
        [InlineKeyboardButton(text=str(_("Orqaga")), callback_data="buy_vip_from_profile")]
    ])

    await callback.message.edit_text(text, reply_markup=kbd, parse_mode="HTML")
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

    if method == "stars":
        prices = [LabeledPrice(label=str(plan["label"]), amount=plan["stars"])]
        currency = "XTR"
        provider_token = None # For Stars it must be None or omitted
        is_test = True # Stars testing
    else:
        # Click
        token = settings.click_provider_token
        if not token or "YOUR_CLICK_TOKEN" in token:
            await callback.answer(str(_("❌ Xatolik yuzaga keldi. Iltimos, keyinroq urinib ko'ring.")), show_alert=True)
            return
        
        # Prices in minor units (UZS * 100)
        prices = [LabeledPrice(label=str(plan["label"]), amount=plan["uzs"] * 100)]
        currency = "UZS"
        provider_token = token
        is_test = True # User said they use test terminal

    try:
        await callback.message.answer_invoice(
            title=str(plan["label"]),
            description=str(_("{days} kunlik VIP obuna uchun to'lov")).format(days=plan["days"]),
            prices=prices,
            payload=f"{plan_key}:{method}",
            provider_token=provider_token,
            currency=currency,
            start_parameter="vip_purchase",
            is_test=is_test
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error sending invoice: {e}")
        error_msg = str(e)
        if "PAYMENT_PROVIDER_INVALID" in error_msg:
            await callback.answer(str(_("❌ To'lov provayderi tokeni noto'g'ri. BotFather'dan olingan tokenni tekshiring.")), show_alert=True)
        else:
            await callback.answer(str(_("❌ Hisob-faktura yuborishda xatolik yuz berdi: {error}")).format(error=error_msg[:50]), show_alert=True)

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
    current_expiry = user.vip_expires_at if user and user.vip_expires_at and user.vip_expires_at > now else now
    new_expiry = current_expiry + timedelta(days=plan["days"])
    
    # Update payment history
    history = user.vip_payment_history or []
    if isinstance(history, dict): history = [history]
    
    amount = plan["stars"] if method == "stars" else plan["uzs"]
    currency_label = "Stars" if method == "stars" else "UZS"

    history.append({
        "date": now.strftime("%d.%m.%Y %H:%M"),
        "amount": amount,
        "currency": currency_label,
        "label": str(plan["label"]),
        "status": "success"
    })
    
    await user_actions.update_user(
        tg_id=message.from_user.id,
        vip_status="active",
        vip_expires_at=new_expiry,
        vip_payment_history=history
    )
    
    await message.answer(
        f"<b>{str(_('To\'lov muvaffaqiyatli!'))}</b>\n\n"
        f"{str(_('VIP:'))} {plan['days']} {str(_('kun'))}\n"
        f"{str(_('Muddati:'))} {new_expiry.strftime('%d.%m.%Y')}",
        parse_mode="HTML"
    )
