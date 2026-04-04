from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.common.i18n import i18n
from src.app.bot.common.utils import get_user_language
from src.app.bot.filters.check_channel_sub import CheckSubscription
from src.app.bot.keyboards.inline import not_channels_button
from src.app.bot.keyboards.replay import get_main_menu
from src.app.database.queries.channels import ChannelActions

_ = i18n.gettext

# Banners for subscription check (reuse existing ones for now)
SUB_BANNERS = {
    "uz": "AgACAgIAAxkBAAICsGnI7MzcPYkSPeYnBFnSaUinvbV7AALhFGsb_utJSv1gCeoq-4aMAQADAgADeAADOgQ",
    "ru": "AgACAgIAAxkBAAICwWnI9rkEQVucoXGjXeDpGWijC69GAAITFWsb_utJSujS1XZlIOrJAQADAgADeAADOgQ",
    "en": "AgACAgIAAxkBAAICxWnI9wx28eppVmST9mRIfuQpk6scAAIfFWsb_utJSriYqPdtMqAbAQADAgADeAADOgQ",
}

# Router for the "Check Subscription" button (Handles click regardless of status)
sub_check_button_router = Router()

check_channel_sub_router = Router()
check_channel_sub_router.message.filter(CheckSubscription())
check_channel_sub_router.callback_query.filter(
    CheckSubscription(),
    ~F.data.in_(["buy_vip_from_profile", "check_sub"]),
    ~F.data.startswith("select_plan:"),
    ~F.data.startswith("pay:"),
)


@check_channel_sub_router.message()
async def check_channel_sub_message(message: Message, session: AsyncSession, bot: Bot):
    channel_actions = ChannelActions(session)
    channel_data = await channel_actions.get_all_channels()

    not_sub_channels = []
    # Filter only mandatory channels
    for channel in channel_data:
        if channel.channel_status == "True":
            try:
                user_status = await bot.get_chat_member(
                    channel.channel_id, message.from_user.id
                )
                if user_status.status not in ["member", "administrator", "creator"]:
                    not_sub_channels.append(channel)
            except Exception as e:
                print(f"Error checking channel {channel.channel_id}: {e}")

    locale = await get_user_language(message.from_user, session)
    i18n.ctx_locale.set(locale)
    banner_id = SUB_BANNERS.get(locale, SUB_BANNERS["uz"])

    await message.answer_photo(
        photo=banner_id,
        caption=_("Botdan foydalanish uchun ushbu kanallarga obuna bo'ling 👇"),
        reply_markup=not_channels_button(not_sub_channels, []),
        parse_mode="HTML",
    )


@check_channel_sub_router.callback_query()
async def check_channel_sub_barrier_callback(
    call: CallbackQuery, session: AsyncSession, bot: Bot
):
    """
    Intercepts generic callbacks if user is NOT subscribed.
    Does NOT handle 'check_sub' because that is handled by sub_check_button_router.
    """
    # If we are here, CheckSubscription is True (user not subscribed)
    # AND it wasn't caught by sub_check_button_router (which should be registered first)

    channel_actions = ChannelActions(session)
    channel_data = await channel_actions.get_all_channels()

    not_sub_channels = []
    for channel in channel_data:
        if channel.channel_status == "True":
            try:
                user_status = await bot.get_chat_member(
                    channel.channel_id, call.from_user.id
                )
                if user_status.status not in ["member", "administrator", "creator"]:
                    not_sub_channels.append(channel)
            except Exception as e:
                pass

    locale = await get_user_language(call.from_user, session)
    i18n.ctx_locale.set(locale)
    banner_id = SUB_BANNERS.get(locale, SUB_BANNERS["uz"])

    await call.message.answer_photo(
        photo=banner_id,
        caption=_("Botdan foydalanish uchun ushbu kanallarga obuna bo'ling 👇"),
        reply_markup=not_channels_button(not_sub_channels, []),
        parse_mode="HTML",
    )
    await call.answer()


@sub_check_button_router.callback_query(F.data == "check_sub")
async def on_check_subscription_button(
    call: CallbackQuery, session: AsyncSession, bot: Bot
):
    channel_actions = ChannelActions(session)
    channel_data = await channel_actions.get_all_channels()

    not_sub_channels = []
    for channel in channel_data:
        if channel.channel_status == "True":
            try:
                user_status = await bot.get_chat_member(
                    channel.channel_id, call.from_user.id
                )
                if user_status.status not in ["member", "administrator", "creator"]:
                    not_sub_channels.append(channel)
            except Exception as e:
                print(f"Error checking channel {channel.channel_id}: {e}")

    if not_sub_channels:
        # User is still not subscribed
        await call.answer(
            _("❌ Siz hali hamma kanallarga obuna bo'lmadingiz!"), show_alert=True
        )
    else:
        # User subscribed successfully
        try:
            await call.message.delete()
        except:
            pass

        name = (
            call.from_user.first_name
            or call.from_user.last_name
            or call.from_user.full_name
            or "Do'stim"
        )

        # Send new message with ReplyMarkup
        await call.message.answer(
            _(
                """<b>👋 Salom {name}</b>

<b>Botimizga xush kelibsiz.</b>

<b>🍿 Kino kodini yuboring:</b>"""
            ).format(name=name),
            reply_markup=get_main_menu(),
        )
