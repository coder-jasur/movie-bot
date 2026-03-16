from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from src.app.bot.common.buttons import (
    BTN_MOVIES, BTN_ANIME, BTN_CARTOON, BTN_FAVORITES,
    BTN_VIP, BTN_PROFILE,
    BTN_BACK,
    BTN_RND_FILM, BTN_RND_SERIES, BTN_RND_MINI, BTN_TOP_MOVIES, BTN_GENRE_MOVIES,
    BTN_RND_ANIME, BTN_RND_ANIME_SERIES, BTN_RND_ANIME_MINI, BTN_TOP_ANIME, BTN_GENRE_ANIME,
    BTN_RND_CARTOON, BTN_RND_CARTOON_SERIES, BTN_RND_CARTOON_MINI, BTN_TOP_CARTOON, BTN_GENRE_CARTOON
)
from src.app.bot.common.i18n import i18n


# ========== ASOSIY MENYU ==========
def get_main_menu() -> ReplyKeyboardMarkup:
    _ = i18n.gettext
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=str(BTN_MOVIES)),
                KeyboardButton(text=str(BTN_ANIME)),
                KeyboardButton(text=str(BTN_CARTOON)),
            ],
            [
                KeyboardButton(text=str(BTN_FAVORITES)),
            ],
            [
                KeyboardButton(text=str(BTN_VIP)),
                KeyboardButton(text=str(BTN_PROFILE)),
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder=str(_("Kategoriyani tanlang..."))
    )


# ========== KATEGORIYA SUB-MENYULARI ==========
def get_cinema_menu() -> ReplyKeyboardMarkup:
    _ = i18n.gettext
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=str(BTN_RND_FILM)),
                KeyboardButton(text=str(BTN_RND_SERIES)),
            ],
            [
                KeyboardButton(text=str(BTN_RND_MINI)),
            ],
            [
                KeyboardButton(text=str(BTN_TOP_MOVIES)),
                KeyboardButton(text=str(BTN_GENRE_MOVIES)),
            ],
            [
                KeyboardButton(text=str(BTN_BACK)),
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder=str(_("Kontent turini tanlang..."))
    )


def get_anime_menu() -> ReplyKeyboardMarkup:
    _ = i18n.gettext
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=str(BTN_RND_ANIME)),
                KeyboardButton(text=str(BTN_RND_ANIME_SERIES)),
            ],
            [
                KeyboardButton(text=str(BTN_RND_ANIME_MINI)),
            ],
            [
                KeyboardButton(text=str(BTN_TOP_ANIME)),
                KeyboardButton(text=str(BTN_GENRE_ANIME)),
            ],
            [
                KeyboardButton(text=str(BTN_BACK)),
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder=str(_("Anime turini tanlang..."))
    )


def get_cartoon_menu() -> ReplyKeyboardMarkup:
    _ = i18n.gettext
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=str(BTN_RND_CARTOON)),
                KeyboardButton(text=str(BTN_RND_CARTOON_SERIES)),
            ],
            [
                KeyboardButton(text=str(BTN_RND_CARTOON_MINI)),
            ],
            [
                KeyboardButton(text=str(BTN_TOP_CARTOON)),
                KeyboardButton(text=str(BTN_GENRE_CARTOON)),
            ],
            [
                KeyboardButton(text=str(BTN_BACK)),
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder=str(_("Multfilm turini tanlang..."))
    )