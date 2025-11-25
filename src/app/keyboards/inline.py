from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.app.keyboards.callback_data import FeatureFilmsCD, SeriesCD, MiniSeriesCD, SeriesPlayerCD, FeatureFilmPlayerCD, \
    MiniSeriesPlayerCD, ActionType, DeleteMovie, ChannelsCD, BotCD

choose_movie_type = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="фильм", callback_data="feature_films")
        ],
        [
            InlineKeyboardButton(text="сериал", callback_data="series")
        ],
        [
            InlineKeyboardButton(text="фильм с эпизодами", callback_data="mini_series")
        ],
        [
            InlineKeyboardButton(text="назад", callback_data="back_to_admin_menu")
        ]
    ]
)

add_feature_films_menu_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="добавить код",
                callback_data=FeatureFilmsCD(actions="add_movie_code").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить название фильиа",
                callback_data=FeatureFilmsCD(actions="add_movie_name").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить видео",
                callback_data=FeatureFilmsCD(actions="add_movie_media").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить описание",
                callback_data=FeatureFilmsCD(actions="add_movie_caption").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить √",
                callback_data=FeatureFilmsCD(actions="add_movie").pack()
            )
        ],
        [
            InlineKeyboardButton(text="назад", callback_data="back_to_movie_setup")
        ]
    ]
)

add_series_menu_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="добавить код",
                callback_data=SeriesCD(actions="add_movie_code").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить название фильиа",
                callback_data=SeriesCD(actions="add_movie_name").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить видео",
                callback_data=SeriesCD(actions="add_movie_media").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить описание",
                callback_data=SeriesCD(actions="add_movie_caption").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить серию",
                callback_data=SeriesCD(actions="add_movie_series").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить сезон",
                callback_data=SeriesCD(actions="add_movie_season").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить √",
                callback_data=SeriesCD(actions="add_movie").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="назад",
                callback_data="back_to_movie_setup"
            )
        ]
    ]
)

add_mini_series_menu_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="добавить код",
                callback_data=MiniSeriesCD(actions="add_movie_code").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить название фильиа",
                callback_data=MiniSeriesCD(actions="add_movie_name").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить видео",
                callback_data=MiniSeriesCD(actions="add_movie_media").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить описание",
                callback_data=MiniSeriesCD(actions="add_movie_caption").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить серию",
                callback_data=MiniSeriesCD(actions="add_movie_series").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="добавить √",
                callback_data=MiniSeriesCD(actions="add_movie").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="назад",
                callback_data="back_to_movie_setup"
            )
        ]
    ]
)

admin_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="добавить фильм", callback_data="add_movie")
        ],
        [
            InlineKeyboardButton(text="удалить фильм", callback_data="delete_movie")
        ],
        [
            InlineKeyboardButton(text="рассылка", callback_data="broadcast")
        ],
        [
            InlineKeyboardButton(text="обязательные подписки", callback_data="mandatory_subscriptions")
        ],
        [
            InlineKeyboardButton(text="количесво пользывателей ", callback_data="users_count")
        ]
    ]
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
) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()

    nav_buttons = []

    if int(current_series_for_current_season) > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Предыдущая серия",
                callback_data=SeriesPlayerCD(
                    code=code,
                    series_number=current_series_for_current_season - 1,
                    season_number=current_season,
                    all_series_numebr=current_series - 1,
                    action=ActionType.back_series
                ).pack()
            )
        )

    # Серия номер
    nav_buttons.append(
        InlineKeyboardButton(
            text=f"{current_series_for_current_season}/{series_count_for_current_season}",
            callback_data="noop"
        )
    )

    # Следующая серия
    if current_series_for_current_season < series_count_for_current_season:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Следующая серия ➡️",
                callback_data=SeriesPlayerCD(
                    code=code,
                    series_number=current_series_for_current_season + 1,
                    season_number=current_season,
                    all_series_numebr=current_series + 1,
                    action=ActionType.next_series
                ).pack()
            )
        )

    keyboard.row(*nav_buttons)

    # 🔢 Общий номер серии (например 4/30)
    if series_count > 1:
        keyboard.row(
            InlineKeyboardButton(
                text=f"{current_series}/{series_count}",
                callback_data="noop"
            )
        )

    # 📺 Навигация по сезонам
    season_buttons = []
    if seasons_count > 1:
        # Предыдущий сезон
        if current_season > 1:
            season_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Предыдущий сезон",
                    callback_data=SeriesPlayerCD(
                        code=code,
                        series_number=1,
                        season_number=current_season - 1,
                        all_series_numebr=current_series,
                        action=ActionType.back_season
                    ).pack()
                )
            )

        # Номер сезона
        if seasons_count > 1:
            season_buttons.append(
                InlineKeyboardButton(
                    text=f"{current_season}/{seasons_count}",
                    callback_data="noop"
                )
            )

        # Следующий сезон
        if current_season < seasons_count:
            season_buttons.append(
                InlineKeyboardButton(
                    text="Следующий сезон ➡️",
                    callback_data=SeriesPlayerCD(
                        code=code,
                        series_number=1,
                        season_number=current_season + 1,
                        all_series_numebr=current_series,
                        action=ActionType.next_season
                    ).pack()
                )
            )

        keyboard.row(*season_buttons)

    # ⭐ Кнопка избранного
    if saved:
        keyboard.row(
            InlineKeyboardButton(
                text="🗑 Удалить из избранного",
                callback_data=SeriesPlayerCD(
                    code=code,
                    series_number=current_series_for_current_season,
                    season_number=current_season,
                    all_series_numebr=current_series,
                    action=ActionType.remove_in_favorites
                ).pack()
            )
        )
    else:
        keyboard.row(
            InlineKeyboardButton(
                text="💾 Сохранить",
                callback_data=SeriesPlayerCD(
                    code=code,
                    series_number=current_series_for_current_season,
                    season_number=current_season,
                    all_series_numebr=current_series,
                    action=ActionType.save_to_favorites
                ).pack()
            )
        )

    keyboard.row(InlineKeyboardButton(
        text="❌", callback_data="close"
    ))

    return keyboard.as_markup()


def film_kbd(code: int, saved: bool) -> InlineKeyboardMarkup:
    inline_keyboard = InlineKeyboardBuilder()

    film_kbd_clouse_for_series = InlineKeyboardButton(
        text="❌", callback_data="close"
    )

    if saved:
        add_to_favorites = InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=FeatureFilmPlayerCD(
                code=code,
                actions="delete_for_favorites"
            ).pack()
        )
    else:
        add_to_favorites = InlineKeyboardButton(
            text="💾 Сохранить",
            callback_data=FeatureFilmPlayerCD(
                code=code,
                actions="add_to_favorites"
            ).pack()
        )

    inline_keyboard.row(add_to_favorites)
    inline_keyboard.row(film_kbd_clouse_for_series)

    return inline_keyboard.as_markup()


def mini_series_player_kbd(code: int, current_seria: int, serias_count: int, saved: bool) -> InlineKeyboardMarkup:
    inline_keyboard = InlineKeyboardBuilder()

    serias_info_button = InlineKeyboardButton(text=f'{current_seria}/{serias_count}', callback_data="serias_info")
    next_button = InlineKeyboardButton(
        text='Следующая серия ⏭️',
        callback_data=MiniSeriesPlayerCD(code=code, series_number=current_seria + 1,
                                         action=ActionType.next_series).pack()
    )
    previous_button = InlineKeyboardButton(
        text='⏮️ Назад',
        callback_data=MiniSeriesPlayerCD(code=code, series_number=current_seria - 1,
                                         action=ActionType.back_series).pack()
    )

    film_kbd_clouse_for_series = InlineKeyboardButton(
        text="❌", callback_data="close"
    )

    if saved:
        add_to_favorites = InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=MiniSeriesPlayerCD(
                code=code,
                series_number=current_seria,
                action="delete_for_favorites"
            ).pack()
        )
    else:
        add_to_favorites = InlineKeyboardButton(
            text="💾 Сохранить",
            callback_data=MiniSeriesPlayerCD(
                code=code,
                series_number=current_seria,
                action="add_to_favorites"
            ).pack()
        )

    if serias_count > 1:
        if current_seria == 1:
            inline_keyboard.row(serias_info_button, next_button)
        elif 1 < current_seria < serias_count:
            inline_keyboard.row(previous_button, serias_info_button, next_button)
        else:
            inline_keyboard.row(previous_button, serias_info_button)

    inline_keyboard.row(add_to_favorites)
    inline_keyboard.row(film_kbd_clouse_for_series)

    return inline_keyboard.as_markup()



def confirm_delete_kbd(code: int, action: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Да",
                callback_data=DeleteMovie(action=action, code=code, season=0, series=0).pack()
            ),
            InlineKeyboardButton(
                text="Нет",
                callback_data="back_to_admin_menu"
            )
        ]
    ])


def mini_series_choice_kbd(code: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🧩 удалить епизод",
                callback_data=DeleteMovie(action="delete_mini_series_epizod", code=code, season=0, series=0).pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="🗑️ удалить полнатю ",
                callback_data=DeleteMovie(action="delete_mini_series_all", code=code, season=0, series=0).pack()
            )
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back_to_admin_menu")
        ]
    ])


def series_choice_kbd(code: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🗑 удалить полнатю ",
        callback_data=DeleteMovie(code=code, action="delete_series_all", season=0, series=0).pack()
    )
    builder.button(
        text="📂 удалить сезон",
        callback_data=DeleteMovie(code=code, action="delete_series_season", season=0, series=0).pack()
    )
    builder.button(
        text="удалить епизод",
        callback_data=DeleteMovie(code=code, action="delete_series_epizod", season=0, series=0).pack()
    )
    builder.button(
        text="Назад",
        callback_data="back_to_admin_menu"
    )
    builder.adjust(1)
    return builder.as_markup()


back_to_admin_menu_kbd = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Назад", callback_data="back_to_admin_menu")
        ]
    ]
)

start_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Telegram", url="https://t.me/KinoLentaUzb")
        ]
    ]
)


def mandatory_sub_kbd(bots_list: list, channels_list: list):
    keyboard = InlineKeyboardBuilder()

    if channels_list:
        keyboard.row(InlineKeyboardButton(text="📥 канали", callback_data="some_call"))
        for channel in channels_list:
            keyboard.row(InlineKeyboardButton(
                text=channel[1],
                callback_data=ChannelsCD(
                    channel_id=channel[0],
                    actions="set_up_menu"
                ).pack()
            )
            )

    if bots_list:
        keyboard.row(InlineKeyboardButton(text="📥 боты", callback_data="some_call"))
        for bot in bots_list:
            keyboard.row(InlineKeyboardButton(
                text=bot[0],
                callback_data=BotCD(
                    bot_username=bot[1],
                    actions="set_up_menu"
                ).pack()
            )
            )

    keyboard.row(InlineKeyboardButton(text="дабавить бот"))
    keyboard.row(InlineKeyboardButton(text="дабавить канал"))

    return keyboard.as_markup()


def not_channels_button(channel_data):
    builder_button = InlineKeyboardBuilder()
    for channel in channel_data:

        builder_button.row(
            InlineKeyboardButton(text=channel[1], url=channel[5])
        )

    builder_button.row(InlineKeyboardButton(text="✅", callback_data="check_sub"))
    return builder_button.as_markup()
