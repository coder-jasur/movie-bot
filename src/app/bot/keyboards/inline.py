from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.app.bot.common.i18n import i18n
from src.app.bot.common.i18n import lazy_gettext as _
from src.app.bot.common.utils import get_lang_code
from src.app.bot.keyboards.callback_data import (
    ActionType,
    FeatureFilmPlayerCD,
    MiniSeriesPlayerCD,
    SeriesPlayerCD,
)


def series_player_kbd(
    code: int,
    current_series: int,
    series_count: int,
    current_season: int,
    seasons_count: int,
    current_series_for_current_season: int,
    series_count_for_current_season: int,
    saved: bool,
    files: dict = None,
    current_quality: str = "original",
    current_language: str = "uz",
    show_quality_menu: bool = False,
    show_language_menu: bool = False,
    is_vip: bool = False,
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()

    # Quality menu
    if show_quality_menu:
        lang_files = files.get(current_language, {}) if isinstance(files, dict) else {}
        return _build_quality_menu(
            files=lang_files,
            current_quality=current_quality,
            current_language=current_language,
            cd_builder=lambda q, act: SeriesPlayerCD(
                code=code,
                series_number=current_series_for_current_season,
                season_number=current_season,
                all_series_numebr=current_series,
                action=act,
                quality=q,
                language=current_language,
            ).pack(),
            back_action=ActionType.close_quality_menu,
            is_vip=is_vip,
        )

    # Language menu
    if show_language_menu:
        return _build_language_menu(
            files=files,
            current_quality=current_quality,
            current_language=current_language,
            cd_builder=lambda l, act: SeriesPlayerCD(
                code=code,
                series_number=current_series_for_current_season,
                season_number=current_season,
                all_series_numebr=current_series,
                action=act,
                quality=current_quality,
                language=l,
            ).pack(),
            back_action=ActionType.close_quality_menu,  # Reuse close quality for back
        )

    # --- NAVIGATION ROW (Episodes) ---
    nav_buttons = []
    if int(current_series_for_current_season) > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text=str(_("⬅️ Oldingi qism")),
                callback_data=SeriesPlayerCD(
                    code=code,
                    series_number=current_series_for_current_season - 1,
                    season_number=current_season,
                    all_series_numebr=current_series - 1,
                    action=ActionType.back_series,
                    quality=current_quality,
                    language=current_language,
                ).pack(),
            )
        )

    nav_buttons.append(
        InlineKeyboardButton(
            text=f"{current_series_for_current_season}/{series_count_for_current_season}",
            callback_data=SeriesPlayerCD(
                code=code,
                series_number=current_series_for_current_season,
                season_number=current_season,
                all_series_numebr=current_series,
                action=ActionType.open_series_menu,
                quality=current_quality,
                language=current_language,
            ).pack(),
        )
    )

    if current_series_for_current_season < series_count_for_current_season:
        nav_buttons.append(
            InlineKeyboardButton(
                text=str(_("Keyingi qism ➡️")),
                callback_data=SeriesPlayerCD(
                    code=code,
                    series_number=current_series_for_current_season + 1,
                    season_number=current_season,
                    all_series_numebr=current_series + 1,
                    action=ActionType.next_series,
                    quality=current_quality,
                    language=current_language,
                ).pack(),
            )
        )

    keyboard.row(*nav_buttons)
    if series_count > 1:
        keyboard.row(
            InlineKeyboardButton(
                text=f"{current_series}/{series_count}", callback_data="noop"
            )
        )
    # --- NAVIGATION ROW (Total Count or Seasons) ---
    if seasons_count > 1:
        season_nav = []
        if current_season > 1:
            season_nav.append(
                InlineKeyboardButton(
                    text=str(_("⬅️ Oldingi fasl")),
                    callback_data=SeriesPlayerCD(
                        code=code,
                        series_number=1,
                        season_number=current_season - 1,
                        all_series_numebr=current_series,
                        action=ActionType.back_season,
                        quality=current_quality,
                        language=current_language,
                    ).pack(),
                )
            )

        season_nav.append(
            InlineKeyboardButton(
                text=f"{current_season}/{seasons_count}",
                callback_data=SeriesPlayerCD(
                    code=code,
                    series_number=current_series_for_current_season,
                    season_number=current_season,
                    all_series_numebr=current_series,
                    action=ActionType.open_seasons_menu,
                    quality=current_quality,
                    language=current_language,
                ).pack(),
            )
        )

        if current_season < seasons_count:
            season_nav.append(
                InlineKeyboardButton(
                    text=str(_("Keyingi fasl ➡️")),
                    callback_data=SeriesPlayerCD(
                        code=code,
                        series_number=1,
                        season_number=current_season + 1,
                        all_series_numebr=current_series,
                        action=ActionType.next_season,
                        quality=current_quality,
                        language=current_language,
                    ).pack(),
                )
            )
        keyboard.row(*season_nav)

    # --- SETTINGS ROW (Language & Quality) ---
    settings_row = []
    if isinstance(files, dict) and len(files) > 1:
        has_real_langs = any(
            not str(k).lower().endswith("p") and str(k).lower() != "original"
            for k in files.keys()
        )
        if has_real_langs:
            from src.app.bot.common.languages import LANGUAGES

            lang_obj = next(
                (l for l in LANGUAGES if l["id"] == get_lang_code(current_language)),
                None,
            )
            lang_label = lang_obj["label"] if lang_obj else current_language.upper()
            settings_row.append(
                InlineKeyboardButton(
                    text=f"🌐 {lang_label}",
                    callback_data=SeriesPlayerCD(
                        code=code,
                        series_number=current_series_for_current_season,
                        season_number=current_season,
                        all_series_numebr=current_series,
                        action=ActionType.open_language_menu,
                        quality=current_quality,
                        language=get_lang_code(current_language),
                    ).pack(),
                )
            )

    lang_files = files.get(current_language, {}) if isinstance(files, dict) else {}
    if isinstance(lang_files, dict):
        selectable_qualities = [k for k in lang_files.keys()]
        if selectable_qualities:
            # Avoid showing "Original" as a label
            quality_display = (
                current_quality
                if str(current_quality).strip().lower() != "original"
                else "HD"
            )
            settings_row.append(
                InlineKeyboardButton(
                    text=f"⚙️ {quality_display}",
                    callback_data=SeriesPlayerCD(
                        code=code,
                        series_number=current_series_for_current_season,
                        season_number=current_season,
                        all_series_numebr=current_series,
                        action=ActionType.open_quality_menu,
                        quality=current_quality,
                        language=get_lang_code(current_language),
                    ).pack(),
                )
            )

    if settings_row:
        keyboard.row(*settings_row)

    # --- ACTION ROW (Save/Remove) ---
    if saved:
        keyboard.row(
            InlineKeyboardButton(
                text=f"🗑 {str(_('O\'chirish'))}",
                callback_data=SeriesPlayerCD(
                    code=code,
                    series_number=current_series_for_current_season,
                    season_number=current_season,
                    all_series_numebr=current_series,
                    action=ActionType.remove_in_favorites,
                    quality=current_quality,
                    language=current_language,
                ).pack(),
            )
        )
    else:
        keyboard.row(
            InlineKeyboardButton(
                text=f"💾 {str(_('Saqlash'))}",
                callback_data=SeriesPlayerCD(
                    code=code,
                    series_number=current_series_for_current_season,
                    season_number=current_season,
                    all_series_numebr=current_series,
                    action=ActionType.save_to_favorites,
                    quality=current_quality,
                    language=current_language,
                ).pack(),
            )
        )

    bottom_row = [InlineKeyboardButton(text="❌", callback_data="close")]
    keyboard.row(*bottom_row)

    return keyboard.as_markup()


def _build_language_menu(
    files: dict, current_quality: str, current_language: str, cd_builder, back_action
):
    from src.app.bot.common.languages import LANGUAGES

    keyboard = InlineKeyboardBuilder()

    items = files.keys() if isinstance(files, dict) else []
    for lang_key in items:
        lang_code = get_lang_code(lang_key)
        lang_obj = next((l for l in LANGUAGES if l["id"] == lang_code), None)
        label = str(lang_obj["label"]) if lang_obj else str(lang_key).upper()

        is_selected = "✅ " if get_lang_code(current_language) == lang_code else ""
        keyboard.row(
            InlineKeyboardButton(
                text=f"{is_selected}{label}",
                callback_data=cd_builder(lang_code, ActionType.set_language),
            )
        )

    keyboard.row(
        InlineKeyboardButton(
            text=str(_("🔙 Orqaga")),
            callback_data=cd_builder(get_lang_code(current_language), back_action),
        )
    )
    return keyboard.as_markup()


def _build_series_list_menu(
    serias_count: int, current_seria: int, cd_builder, back_action
):
    keyboard = InlineKeyboardBuilder()

    # Pack buttons in rows of 5
    buttons = []
    for i in range(1, serias_count + 1):
        is_selected = "✅ " if i == current_seria else ""
        buttons.append(
            InlineKeyboardButton(text=f"{is_selected}{i}", callback_data=cd_builder(i))
        )

    keyboard.add(*buttons)
    keyboard.adjust(5)

    keyboard.row(
        InlineKeyboardButton(
            text=str(_("🔙 Orqaga")),
            callback_data=(
                "back_to_player" if not back_action else cd_builder(current_seria)
            ),  # We'll handle this in player.py
        )
    )
    return keyboard.as_markup()


def _build_seasons_list_menu(
    seasons_count: int, current_season: int, cd_builder, back_action
):
    keyboard = InlineKeyboardBuilder()

    for i in range(1, seasons_count + 1):
        is_selected = "✅ " if i == current_season else ""
        keyboard.row(
            InlineKeyboardButton(
                text=f"{is_selected}{i}-{str(_('Fasl'))}", callback_data=cd_builder(i)
            )
        )

    keyboard.row(
        InlineKeyboardButton(
            text=str(_("🔙 Orqaga")), callback_data=cd_builder(current_season)
        )
    )
    return keyboard.as_markup()


def _build_quality_menu(
    files: dict,
    current_quality: str,
    current_language: str,
    cd_builder,
    back_action,
    is_vip: bool = False,
):
    keyboard = InlineKeyboardBuilder()

    try:
        keys = list(files.keys()) if isinstance(files, dict) else []

        def q_sort_key(x):
            if x.lower() == "original":
                return 9999
            return int(x.rstrip("p")) if x.rstrip("p").isdigit() else 0

        sorted_qualities = sorted(keys, key=q_sort_key, reverse=True)
        # Remove 'original' from the menu
        sorted_qualities = [q for q in sorted_qualities if q.lower() != "original"]
    except:
        sorted_qualities = [
            q
            for q in (files.keys() if isinstance(files, dict) else [])
            if q.lower() != "original"
        ]

    for quality in sorted_qualities:
        is_selected = (
            "✅ "
            if str(current_quality).strip().lower() == str(quality).strip().lower()
            else ""
        )

        vip_tag = ""
        if not is_vip and quality in ["480p", "720p", "1080p"]:
            vip_tag = " 💎"

        label = quality if quality.lower() != "original" else str(_("Original"))
        keyboard.row(
            InlineKeyboardButton(
                text=f"{is_selected}{label}{vip_tag}",
                callback_data=cd_builder(quality, ActionType.set_quality),
            )
        )

    keyboard.row(
        InlineKeyboardButton(
            text=str(_("🔙 Orqaga")),
            callback_data=cd_builder(current_quality, back_action),
        )
    )

    return keyboard.as_markup()


def film_kbd(
    code: int,
    saved: bool,
    files: dict = None,
    current_quality: str = "original",
    current_language: str = "uz",
    show_quality_menu: bool = False,
    show_language_menu: bool = False,
    is_vip: bool = False,
) -> InlineKeyboardMarkup:
    inline_keyboard = InlineKeyboardBuilder()

    if saved:
        add_to_favorites = InlineKeyboardButton(
            text=str(_("🗑 O'chirish")),
            callback_data=FeatureFilmPlayerCD(
                code=code, actions="delete_for_favorites", quality=current_quality
            ).pack(),
        )
    else:
        add_to_favorites = InlineKeyboardButton(
            text=str(_("💾 Saqlash")),
            callback_data=FeatureFilmPlayerCD(
                code=code, actions="add_to_favorites", quality=current_quality
            ).pack(),
        )

    if show_quality_menu:
        lang_files = files.get(current_language, {}) if isinstance(files, dict) else {}
        return _build_quality_menu(
            files=lang_files,
            current_quality=current_quality,
            current_language=current_language,
            cd_builder=lambda q, act: FeatureFilmPlayerCD(
                code=code, actions=act, quality=q, language=current_language
            ).pack(),
            back_action=ActionType.close_quality_menu,
            is_vip=is_vip,
        )

    if show_language_menu:
        return _build_language_menu(
            files=files,
            current_quality=current_quality,
            current_language=current_language,
            cd_builder=lambda l, act: FeatureFilmPlayerCD(
                code=code, actions=act, quality=current_quality, language=l
            ).pack(),
            back_action=ActionType.close_quality_menu,
        )

    # --- SETTINGS ROW (Language & Quality) ---
    settings_row = []
    if isinstance(files, dict) and len(files) > 1:
        has_real_langs = any(
            not str(k).lower().endswith("p") and str(k).lower() != "original"
            for k in files.keys()
        )
        if has_real_langs:
            from src.app.bot.common.languages import LANGUAGES

            lang_obj = next(
                (l for l in LANGUAGES if l["id"] == get_lang_code(current_language)),
                None,
            )
            lang_label = lang_obj["label"] if lang_obj else current_language.upper()
            settings_row.append(
                InlineKeyboardButton(
                    text=f"🌐 {lang_label}",
                    callback_data=FeatureFilmPlayerCD(
                        code=code,
                        actions=ActionType.open_language_menu,
                        quality=current_quality,
                        language=get_lang_code(current_language),
                    ).pack(),
                )
            )

    lang_files = files.get(current_language, {}) if isinstance(files, dict) else {}
    if isinstance(lang_files, dict):
        selectable_qualities = [k for k in lang_files.keys()]
        if selectable_qualities:
            # Avoid showing "original" label
            quality_display = (
                current_quality
                if str(current_quality).strip().lower() != "original"
                else "HD"
            )
            settings_row.append(
                InlineKeyboardButton(
                    text=f"⚙️ {quality_display}",
                    callback_data=FeatureFilmPlayerCD(
                        code=code,
                        actions=ActionType.open_quality_menu,
                        quality=current_quality,
                        language=get_lang_code(current_language),
                    ).pack(),
                )
            )

    if settings_row:
        inline_keyboard.row(*settings_row)

    # --- ACTION ROW (Save/Remove) ---
    if saved:
        inline_keyboard.row(
            InlineKeyboardButton(
                text=f"🗑 {str(_('O\'chirish'))}",
                callback_data=FeatureFilmPlayerCD(
                    code=code, actions="delete_for_favorites", quality=current_quality
                ).pack(),
            )
        )
    else:
        inline_keyboard.row(
            InlineKeyboardButton(
                text=f"💾 {str(_('Saqlash'))}",
                callback_data=FeatureFilmPlayerCD(
                    code=code, actions="add_to_favorites", quality=current_quality
                ).pack(),
            )
        )

    bottom_row = [InlineKeyboardButton(text="❌", callback_data="close")]
    inline_keyboard.row(*bottom_row)

    return inline_keyboard.as_markup()


def mini_series_player_kbd(
    code: int,
    current_seria: int,
    serias_count: int,
    saved: bool,
    files: dict = None,
    current_quality: str = "original",
    current_language: str = "uz",
    show_quality_menu: bool = False,
    show_language_menu: bool = False,
    is_vip: bool = False,
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()

    # Quality menu
    if show_quality_menu:
        lang_files = files.get(current_language, {}) if isinstance(files, dict) else {}
        return _build_quality_menu(
            files=lang_files,
            current_quality=current_quality,
            current_language=current_language,
            cd_builder=lambda q, act: MiniSeriesPlayerCD(
                code=code,
                series_number=current_seria,
                action=act,
                quality=q,
                language=current_language,
            ).pack(),
            back_action=ActionType.close_quality_menu,
            is_vip=is_vip,
        )

    # Language menu
    if show_language_menu:
        return _build_language_menu(
            files=files,
            current_quality=current_quality,
            current_language=current_language,
            cd_builder=lambda l, act: MiniSeriesPlayerCD(
                code=code,
                series_number=current_seria,
                action=act,
                quality=current_quality,
                language=l,
            ).pack(),
            back_action=ActionType.close_quality_menu,  # Reuse close quality for back
        )

    inline_keyboard = InlineKeyboardBuilder()

    serias_info_button = InlineKeyboardButton(
        text=f"{current_seria}/{serias_count}", callback_data="serias_info"
    )
    next_button = InlineKeyboardButton(
        text=str(_("Keyingi qism ➡️")),
        callback_data=MiniSeriesPlayerCD(
            code=code,
            series_number=current_seria + 1,
            action=ActionType.next_series,
            quality=current_quality,
            language=current_language,
        ).pack(),
    )
    previous_button = InlineKeyboardButton(
        text=str(_("⬅️ Orqaga")),
        callback_data=MiniSeriesPlayerCD(
            code=code,
            series_number=current_seria - 1,
            action=ActionType.back_series,
            quality=current_quality,
            language=current_language,
        ).pack(),
    )

    if saved:
        add_to_favorites = InlineKeyboardButton(
            text=str(_("🗑 O'chirish")),
            callback_data=MiniSeriesPlayerCD(
                code=code,
                series_number=current_seria,
                action="delete_for_favorites",
                language=current_language,
            ).pack(),
        )
    else:
        add_to_favorites = InlineKeyboardButton(
            text=str(_("💾 Saqlash")),
            callback_data=MiniSeriesPlayerCD(
                code=code,
                series_number=current_seria,
                action="add_to_favorites",
                language=current_language,
            ).pack(),
        )

    # --- NAVIGATION ROW (Episodes) ---
    nav_buttons = []
    if current_seria > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text=str(_("⬅️ Oldingi qism")),
                callback_data=MiniSeriesPlayerCD(
                    code=code,
                    series_number=current_seria - 1,
                    action=ActionType.back_series,
                    quality=current_quality,
                    language=current_language,
                ).pack(),
            )
        )

    nav_buttons.append(
        InlineKeyboardButton(
            text=f"{current_seria}/{serias_count}",
            callback_data=MiniSeriesPlayerCD(
                code=code,
                series_number=current_seria,
                action=ActionType.open_series_menu,
                quality=current_quality,
                language=current_language,
            ).pack(),
        )
    )

    if current_seria < serias_count:
        nav_buttons.append(
            InlineKeyboardButton(
                text=str(_("Keyingi qism ➡️")),
                callback_data=MiniSeriesPlayerCD(
                    code=code,
                    series_number=current_seria + 1,
                    action=ActionType.next_series,
                    quality=current_quality,
                    language=current_language,
                ).pack(),
            )
        )

    if len(nav_buttons) > 1:
        inline_keyboard.row(*nav_buttons)

    # --- SETTINGS ROW (Language & Quality) ---
    settings_row = []
    if isinstance(files, dict) and len(files) > 1:
        has_real_langs = any(
            not str(k).lower().endswith("p") and str(k).lower() != "original"
            for k in files.keys()
        )
        if has_real_langs:
            from src.app.bot.common.languages import LANGUAGES

            lang_obj = next(
                (l for l in LANGUAGES if l["id"] == get_lang_code(current_language)),
                None,
            )
            lang_label = lang_obj["label"] if lang_obj else current_language.upper()
            settings_row.append(
                InlineKeyboardButton(
                    text=f"🌐 {lang_label}",
                    callback_data=MiniSeriesPlayerCD(
                        code=code,
                        series_number=current_seria,
                        action=ActionType.open_language_menu,
                        quality=current_quality,
                        language=get_lang_code(current_language),
                    ).pack(),
                )
            )

    lang_files = files.get(current_language, {}) if isinstance(files, dict) else {}
    if isinstance(lang_files, dict):
        selectable_qualities = [k for k in lang_files.keys()]
        if selectable_qualities:
            # Avoid showing "original" label
            quality_display = (
                current_quality
                if str(current_quality).strip().lower() != "original"
                else "HD"
            )
            settings_row.append(
                InlineKeyboardButton(
                    text=f"⚙️ {quality_display}",
                    callback_data=MiniSeriesPlayerCD(
                        code=code,
                        series_number=current_seria,
                        action=ActionType.open_quality_menu,
                        quality=current_quality,
                        language=get_lang_code(current_language),
                    ).pack(),
                )
            )

    if settings_row:
        inline_keyboard.row(*settings_row)

    # --- ACTION ROW (Save/Remove) ---
    if saved:
        inline_keyboard.row(
            InlineKeyboardButton(
                text=f"🗑 {str(_('O\'chirish'))}",
                callback_data=MiniSeriesPlayerCD(
                    code=code,
                    series_number=current_seria,
                    action="delete_for_favorites",
                    language=current_language,
                ).pack(),
            )
        )
    else:
        inline_keyboard.row(
            InlineKeyboardButton(
                text=f"💾 {str(_('Saqlash'))}",
                callback_data=MiniSeriesPlayerCD(
                    code=code,
                    series_number=current_seria,
                    action="add_to_favorites",
                    language=current_language,
                ).pack(),
            )
        )

    bottom_row = [InlineKeyboardButton(text="❌", callback_data="close")]
    inline_keyboard.row(*bottom_row)

    return inline_keyboard.as_markup()


def get_start_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Telegram", url="https://t.me/KinoLentaUzb")]
        ]
    )


def not_channels_button(channel_data, bots_data):
    builder_button = InlineKeyboardBuilder()
    for bot in bots_data:
        builder_button.row(InlineKeyboardButton(text=bot.bot_name, url=bot.bot_url))
    for channel in channel_data:
        builder_button.row(
            InlineKeyboardButton(text=channel.channel_name, url=channel.channel_url)
        )

    builder_button.row(
        InlineKeyboardButton(
            text=str(_("💎 VIP sotib olish")), callback_data="buy_vip_from_profile"
        )
    )
    builder_button.row(
        InlineKeyboardButton(text=str(_("✅ Tekshirish")), callback_data="check_sub")
    )
    return builder_button.as_markup()


def get_instagram_channel_kbd() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=str(_("Instagram Kanal")),
                    url="https://www.instagram.com/film.zonasi/",
                )
            ]
        ]
    )


def get_language_inline_markup() -> InlineKeyboardMarkup:
    from src.app.bot.keyboards.callback_data import LanguageCD

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🇺🇿 O'zbekcha", callback_data=LanguageCD(code="uz").pack()
        ),
        InlineKeyboardButton(
            text="🇷🇺 Русский", callback_data=LanguageCD(code="ru").pack()
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🇺🇸 English", callback_data=LanguageCD(code="en").pack()
        )
    )
    return builder.as_markup()
