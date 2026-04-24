import html
import logging

from aiogram import Bot
from aiogram.enums import ContentType
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Cancel, Row, Start, SwitchTo
from aiogram_dialog.widgets.text import Const, Format
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.common.i18n import lazy_gettext as gettext_
from src.app.bot.states.admin.channel import OPMenu
from src.app.bot.states.admin.dialogs import (
    AddMovieWizardSG,
    AdminManagementSG,
    AdminMenuSG,
    AdminVIPManagerSG,
    BackupSG,
    EditMovieSG,
)
from src.app.bot.states.admin.referral import ReferralSG
from src.app.core.celery_app import is_worker_online
from src.app.core.config import load_config
from src.app.database.queries.admin import AdminActions
from src.app.database.queries.user import UserActions
from src.app.services.broadcaster import Broadcaster

logger = logging.getLogger(__name__)


def get_flag_emoji(lang_code: str) -> str:
    flags = {
        "en": "🇺🇸",
        "ru": "🇷🇺",
        "uz": "🇺🇿",
        "kz": "🇰🇿",
        "uk": "🇺🇦",
        "de": "🇩🇪",
        "fr": "🇫🇷",
        "es": "🇪🇸",
        "it": "🇮🇹",
        "tr": "🇹🇷",
        "ar": "🇦🇪",
        "fa": "🇮🇷",
        "hi": "🇮🇳",
        "zh": "🇨🇳",
        "ja": "🇯🇵",
    }
    if not lang_code:
        return "🏳️"
    code = lang_code.split("-")[0].lower()
    return flags.get(code, "🏳️")


async def get_statistics(dialog_manager: DialogManager, **kwargs):
    session: AsyncSession = dialog_manager.middleware_data["session"]
    user_actions = UserActions(session)
    stats = await user_actions.get_registration_stats()

    # Admin level check for revenue visibility
    user_id = dialog_manager.event.from_user.id
    config = load_config()
    is_super = user_id in config.admins_ids
    if not is_super:
        actions = AdminActions(session)
        level = await actions.get_admin_level(user_id)
        is_super = level >= 2

    rev_text = ""
    if is_super:
        rev = stats.get("revenue", {})

        def fmt_rev(period):
            p = rev.get(period, {"uzs": 0, "stars": 0})
            return f"<b>{p['uzs']:,}</b> / <b>{p['stars']}</b> ⭐"

        rev_text = (
            f"\n💰 <b>{gettext_('Daromadlar:')}</b>\n"
            f"📅 {gettext_('Bugun:')} {fmt_rev('day')}\n"
            f"📆 {gettext_('Hafta:')} {fmt_rev('week')}\n"
            f"🗓 {gettext_('Oy:')} {fmt_rev('month')}\n"
            f"📅 {gettext_('Yil:')} {fmt_rev('year')}\n"
            f"💰 {gettext_('Jami:')} {fmt_rev('total')}\n"
        )

    langs_str = "\n".join(
        [f"   • {get_flag_emoji(l['code'])}: {l['count']}" for l in stats["languages"]]
    )

    return {
        "day": stats["day"],
        "week": stats["week"],
        "month": stats["month"],
        "year": stats["year"],
        "total": stats["total"],
        "premium": stats["premium"],
        "active_vip": stats.get("active_vip", 0),
        "revenue_section": rev_text,
        "languages": langs_str if langs_str else "   • N/A",
        "back_main": gettext_("⬅️ Ortga"),
    }


async def get_labels(dialog_manager: DialogManager, **kwargs):
    session: AsyncSession = dialog_manager.middleware_data["session"]
    actions = AdminActions(session)
    user_id = dialog_manager.event.from_user.id

    config = load_config()

    is_super = user_id in config.admins_ids
    if not is_super:
        level = await actions.get_admin_level(user_id)
        is_super = level >= 2

    worker_online = is_worker_online()
    status_text = (
        gettext_("🟢 Worker: Onlayn")
        if worker_online
        else gettext_("🔴 Worker: Offlayn (Lokal kompyuter yoqilmagan)")
    )

    return {
        "title": f"<b>{gettext_('ADMIN_PANEL_TITLE')}</b>\n\n{status_text}",
        "add": gettext_("BTN_ADD_MOVIE"),
        "edit": gettext_("BTN_EDIT_DELETE"),
        "channels": gettext_("BTN_CHANNELS_BOTS"),
        "broadcast": gettext_("BTN_SEND_BROADCAST"),
        "referrals": gettext_("BTN_REFERRALS"),
        "stats": gettext_("BTN_STATISTICS"),
        "vip_manage": gettext_("BTN_VIP_MANAGEMENT"),
        "admin_manage": gettext_("ADMIN_MANAGMENT"),
        "backup": gettext_("BTN_BACKUP"),
        "auto_posting": gettext_("📢 Auto Posting"),
        "close": gettext_("BTN_CLOSE"),
        "cancel": gettext_("BTN_CANCEL"),
        "confirm": gettext_("BTN_CONFIRM_SEND"),
        "broadcast_input_text": gettext_(
            "📨 <b>Broadcast</b>\n\nBarcha foydalanuvchilarga yuboriladigan xabarni yuboring:\n<i>(matn, rasm, video — istalgan format)</i>"
        ),
        "broadcast_confirm_text": gettext_(
            "⚠️ <b>Broadcast tasdiqlash</b>\n\nXabarni barcha foydalanuvchilarga yuborishni tasdiqlaysizmi?"
        ),
        "worker_online": worker_online,
        "is_super_admin": is_super,
    }


async def on_add_movie_click(c: CallbackQuery, widget: Button, manager: DialogManager):
    if not is_worker_online():
        await c.answer(
            str(
                gettext_(
                    "⚠️ Lokal kompyuterda Worker ishga tushirilmagan! Iltimos, oldin workerni yoqing."
                )
            ),
            show_alert=True,
        )
        return
    await manager.start(AddMovieWizardSG.choose_category)


async def on_edit_movie_click(c: CallbackQuery, widget: Button, manager: DialogManager):
    if not is_worker_online():
        await c.answer(
            str(
                gettext_(
                    "⚠️ Lokal kompyuterda Worker ishga tushirilmagan! Iltimos, oldin workerni yoqing."
                )
            ),
            show_alert=True,
        )
        return
    await manager.start(EditMovieSG.input_code)


async def on_broadcast_message(m: Message, widget, manager: DialogManager):
    manager.dialog_data["broadcast_message_id"] = m.message_id
    manager.dialog_data["broadcast_chat_id"] = m.chat.id
    manager.dialog_data["broadcast_content_type"] = m.content_type.value
    if m.reply_markup:
        manager.dialog_data["broadcast_reply_markup"] = m.reply_markup.model_dump_json()
    await manager.switch_to(AdminMenuSG.broadcast_confirm)


async def run_broadcast_task(
    bot: Bot,
    session_pool,
    admin_id: int,
    from_chat_id: int,
    message_id: int,
    reply_markup_json: str = None,
    exclude_vip: bool = False,
):
    try:
        from aiogram.types import InlineKeyboardMarkup
        reply_markup = None
        if reply_markup_json:
            try:
                reply_markup = InlineKeyboardMarkup.model_validate_json(reply_markup_json)
            except Exception as e:
                logger.error(f"Failed to parse reply markup: {e}")

        async with session_pool() as session:
            broadcaster = Broadcaster(
                bot=bot,
                session=session,
                admin_id=admin_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
                exclude_vip=exclude_vip,
            )
            await broadcaster.broadcast()
    except Exception as e:
        logger.error(f"Fonda xabar yuborishda xatolik: {e}")
        try:
            await bot.send_message(admin_id, f"❌ Fonda xabar yuborishda xatolik: {e}")
        except:
            pass


async def on_broadcast_confirm(c: CallbackQuery, widget, manager: DialogManager):
    bot: Bot = manager.middleware_data["bot"]
    session_pool = manager.middleware_data.get("session_pool")

    message_id = manager.dialog_data.get("broadcast_message_id")
    chat_id = manager.dialog_data.get("broadcast_chat_id")
    reply_markup_json = manager.dialog_data.get("broadcast_reply_markup")

    if not message_id or not chat_id:
        await c.answer(str(gettext_("❌ Xabar topilmadi")), show_alert=True)
        return

    if not session_pool:
        await c.answer("❌ Session pool topilmadi (Error: DP error)", show_alert=True)
        return

    import asyncio

    asyncio.create_task(
        run_broadcast_task(
            bot=bot,
            session_pool=session_pool,
            admin_id=c.from_user.id,
            from_chat_id=chat_id,
            message_id=message_id,
            reply_markup_json=reply_markup_json,
        )
    )

    await c.answer(
        str(gettext_("🚀 Xabar yuborish fonda boshlandi. Tez orada hisobot olasiz.")),
        show_alert=True,
    )
    await manager.switch_to(AdminMenuSG.menu)


admin_main_dialog = Dialog(
    Window(
        Format("{title}"),
        Row(
            Button(Format("{add}"), id="add_movie", on_click=on_add_movie_click),
            Button(Format("{edit}"), id="edit_movie", on_click=on_edit_movie_click),
        ),
        Row(
            Start(Format("{channels}"), id="channels_bots", state=OPMenu.menu),
            SwitchTo(
                Format("{broadcast}"), id="broadcast", state=AdminMenuSG.broadcast_input
            ),
        ),
        Row(
            Start(Format("{referrals}"), id="referrals", state=ReferralSG.menu),
        ),
        Row(
            SwitchTo(Format("{stats}"), id="stats", state=AdminMenuSG.statistics),
            Start(
                Format("{vip_manage}"), id="vip_manage", state=AdminVIPManagerSG.search
            ),
        ),
        Row(
            Start(
                Format("{admin_manage}"),
                id="admin_manage",
                state=AdminManagementSG.list_admins,
                when="is_super_admin",
            ),
        ),
        Row(
            Start(Format("{backup}"), id="backup", state=BackupSG.menu),
            Start(Format("{auto_posting}"), id="auto_posting", state=PostAutoPostingSG.menu),
        ),
        Row(
            Cancel(Format("{close}"), id="close_admin"),
        ),
        state=AdminMenuSG.menu,
        getter=get_labels,
    ),
    Window(
        Format(
            gettext_(
                "📊 <b>Statistika:</b>\n\n"
                "📅 <b>Bugun:</b> {day}\n"
                "📆 <b>Hafta:</b> {week}\n"
                "🗓 <b>Oy:</b> {month}\n"
                "📅 <b>Yil:</b> {year}\n"
                "👥 <b>Jami:</b> {total}\n\n"
                "🌟 <b>Premium:</b> {premium}\n"
                "💎 <b>VIP Foydalanuvchilar:</b> {active_vip}\n"
                "{revenue_section}\n"
                "🌍 <b>Top tillar:</b>\n{languages}"
            )
        ),
        SwitchTo(Format("{back_main}"), id="back_main", state=AdminMenuSG.menu),
        state=AdminMenuSG.statistics,
        getter=get_statistics,
    ),
    Window(
        Format("{broadcast_input_text}"),
        MessageInput(on_broadcast_message, content_types=ContentType.ANY),
        SwitchTo(Format("{cancel}"), id="cancel_broadcast", state=AdminMenuSG.menu),
        state=AdminMenuSG.broadcast_input,
        getter=get_labels,
    ),
    Window(
        Format("{broadcast_confirm_text}"),
        Button(
            Format("{confirm}"), id="confirm_broadcast", on_click=on_broadcast_confirm
        ),
        SwitchTo(Format("{cancel}"), id="cancel_confirm", state=AdminMenuSG.menu),
        state=AdminMenuSG.broadcast_confirm,
        getter=get_labels,
    ),
)
