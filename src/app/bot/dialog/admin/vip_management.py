from datetime import timedelta

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Back, Button, Cancel, Row, SwitchTo
from aiogram_dialog.widgets.text import Case, Const, Format
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.common.i18n import lazy_gettext as _
from src.app.bot.handlers.user.account import get_tashkent_time
from src.app.bot.states.admin.dialogs import AdminVIPManagerSG
from src.app.database.queries.user import UserActions


async def get_user_data(dialog_manager: DialogManager, **kwargs):
    session: AsyncSession = dialog_manager.middleware_data["session"]
    user_actions = UserActions(session)
    user_id = dialog_manager.dialog_data.get("target_user_id")

    # Bazaviy interfeys matnlari har doim qaytarilishi shart
    data = {
        "no_user": True,
        "back_btn": _("⬅️ Ortga"),
        "search_back_btn": _("⬅️ Qidiruvga qaytish"),
        "grant_1_btn": _("+1 kun"),
        "grant_10_btn": _("+10 kun"),
        "grant_30_btn": _("+1 oy"),
        "grant_90_btn": _("+3 oy"),
        "grant_unlimited_btn": _("♾ Cheksiz"),
        "revoke_btn": _("❌ VIPni bekor qilish"),
    }

    if not user_id:
        return data

    user = await user_actions.get_user(user_id)
    if not user:
        return data

    now = get_tashkent_time()
    is_vip = user.vip_status == "active" and (
        user.vip_expires_at is None or user.vip_expires_at > now
    )

    expiry_str = (
        _("Cheksiz")
        if user.vip_expires_at is None
        else user.vip_expires_at.strftime("%d.%m.%Y %H:%M")
    )

    data.update(
        {
            "no_user": False,
            "username": user.username or "N/A",
            "tg_id": user.tg_id,
            "is_vip": is_vip,
            "vip_status_text": _("Faol") if is_vip else _("Mavjud emas"),
            "expiry": expiry_str if is_vip else "—",
        }
    )
    return data


async def on_username_input(message: Message, widget, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    user_actions = UserActions(session)

    username = message.text.strip()
    user = await user_actions.get_user_by_username(username)

    if not user:
        # Try if it's an ID
        if username.isdigit():
            user = await user_actions.get_user(int(username))

    if not user:
        await message.answer(str(_("❌ Foydalanuvchi topilmadi.")))
        return

    manager.dialog_data["target_user_id"] = user.tg_id
    await manager.switch_to(AdminVIPManagerSG.user_details)


async def grant_vip(callback: CallbackQuery, button: Button, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    user_actions = UserActions(session)
    user_id = manager.dialog_data.get("target_user_id")

    days_map = {
        "grant_1": 1,
        "grant_10": 10,
        "grant_30": 30,
        "grant_90": 90,
        "grant_unlimited": None,
    }

    days = days_map.get(button.widget_id)
    now = get_tashkent_time()

    # Calculate new expiry and price mapping for statistics
    user = await user_actions.get_user(user_id)
    if not user:
        return

    # Price mapping for statistics (same as account.py)
    price_map = {
        1: 3000,
        10: 18000,
        30: 29000,
        90: 69000,
        None: 100000,  # Unlimited manual grant as a reference price
    }

    if days is None:
        new_expiry = None  # Unlimited
    else:
        current_expiry = (
            user.vip_expires_at
            if user.vip_expires_at and user.vip_expires_at > now
            else now
        )
        new_expiry = current_expiry + timedelta(days=days)

    # Update payment history for statistics
    history = list(user.vip_payment_history or [])
    if isinstance(history, dict):
        history = [history]

    amount = price_map.get(days, 0)
    history.append(
        {
            "date": now.strftime("%d.%m.%Y %H:%M"),
            "amount": amount,
            "currency": "UZS",
            "label": f"Admin: {days} kun" if days else "Admin: Cheksiz",
            "status": "success",
        }
    )

    await user_actions.update_user(
        tg_id=user_id,
        vip_status="active",
        vip_expires_at=new_expiry,
        vip_payment_history=history,
    )

    await callback.answer(str(_("✅ VIP status berildi.")))


async def revoke_vip(callback: CallbackQuery, button: Button, manager: DialogManager):
    session: AsyncSession = manager.middleware_data["session"]
    user_actions = UserActions(session)
    user_id = manager.dialog_data.get("target_user_id")

    await user_actions.update_user(
        tg_id=user_id,
        vip_status="expired",
        vip_expires_at=get_tashkent_time() - timedelta(seconds=1),
    )

    await callback.answer(str(_("❌ VIP status olib qo'yildi.")))


vip_management_dialog = Dialog(
    Window(
        Format(
            _(
                "🔍 <b>Foydalanuvchini qidirish</b>\n\nFoydalanuvchi username (masalan: @username) yoki telegram ID sini yuboring:"
            )
        ),
        MessageInput(on_username_input),
        Cancel(Format("{back_btn}")),
        state=AdminVIPManagerSG.search,
        getter=get_user_data,
    ),
    Window(
        Format(
            _(
                "👤 <b>Foydalanuvchi ma'lumotlari:</b>\n\n🆔 ID: <code>{tg_id}</code>\n👤 Username: @{username}\n💎 VIP: {vip_status_text}\n📅 Muddati: {expiry}"
            )
        ),
        Row(
            Button(Format("{grant_1_btn}"), id="grant_1", on_click=grant_vip),
            Button(Format("{grant_10_btn}"), id="grant_10", on_click=grant_vip),
        ),
        Row(
            Button(Format("{grant_30_btn}"), id="grant_30", on_click=grant_vip),
            Button(Format("{grant_90_btn}"), id="grant_90", on_click=grant_vip),
        ),
        Button(
            Format("{grant_unlimited_btn}"), id="grant_unlimited", on_click=grant_vip
        ),
        Button(Format("{revoke_btn}"), id="revoke", on_click=revoke_vip, when="is_vip"),
        Back(Format("{search_back_btn}")),
        state=AdminVIPManagerSG.user_details,
        getter=get_user_data,
    ),
)
