import logging

from aiogram import F, Router
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.common.buttons import (
    BTN_ANIME,
    BTN_BACK,
    BTN_CARTOON,
    BTN_FAVORITES,
    BTN_GENRE_ANIME,
    BTN_GENRE_CARTOON,
    BTN_GENRE_MOVIES,
    BTN_MOVIES,
    BTN_RND_ANIME,
    BTN_RND_ANIME_MINI,
    BTN_RND_ANIME_SERIES,
    BTN_RND_CARTOON,
    BTN_RND_CARTOON_MINI,
    BTN_RND_CARTOON_SERIES,
    BTN_RND_FILM,
    BTN_RND_MINI,
    BTN_RND_SERIES,
    BTN_TOP_ANIME,
    BTN_TOP_CARTOON,
    BTN_TOP_MOVIES,
)
from src.app.bot.common.genres import GENRES, deserialize_genres, get_genre_display_text
from src.app.bot.common.i18n import i18n
from src.app.bot.common.utils import (
    get_localized_name,
    get_user_language,
    resolve_movie_media,
)
from src.app.bot.keyboards.inline import (
    film_kbd,
    get_instagram_channel_kbd,
    mini_series_player_kbd,
    series_player_kbd,
)
from src.app.bot.keyboards.replay import (
    get_anime_menu,
    get_cartoon_menu,
    get_cinema_menu,
    get_main_menu,
)
from src.app.bot.states.user.dialogs import SearchByGenreSG
from src.app.core.config import load_config
from src.app.database.models import (
    AnimeFeature,
    AnimeMiniSeries,
    AnimeSeries,
    FeatureFilm,
    MiniSeries,
    MultiFilmFeature,
    MultiFilmMiniSeries,
    MultiFilmSeries,
    Series,
)
from src.app.database.queries.movie.anime import (
    AnimeFeatureActions,
    AnimeMiniSeriesActions,
    AnimeSeriesActions,
)
from src.app.database.queries.movie.favorite_movies import FavoriteMoviesActions
from src.app.database.queries.movie.feature_films import FeatureFilmsActions
from src.app.database.queries.movie.mini_series import MiniSeriesActions
from src.app.database.queries.movie.multi_films import (
    MultiFilmFeatureActions,
    MultiFilmMiniSeriesActions,
    MultiFilmSeriesActions,
)
from src.app.database.queries.movie.series import SeriesActions
from src.app.database.queries.movie.top_movies import TopMoviesActions
from src.app.database.queries.user import UserActions
from src.app.repositories.repository import SearchRepository
from src.app.services.view_tracker import ViewTracker

_ = i18n.gettext

logger = logging.getLogger(__name__)

movie_search_router = Router()

# ─────────────────────────────────────────────
# KONTENT TURI TARJIMALARI (3 tilda)
# ─────────────────────────────────────────────
TYPE_TRANSLATIONS = {
    "Film": {"uz": "Film", "ru": "Фильм", "en": "Film"},
    "Serial": {"uz": "Serial", "ru": "Сериал", "en": "Series"},
    "Epizodli film": {
        "uz": "Epizodli film",
        "ru": "Фильм с эпизодами",
        "en": "Film with episodes",
    },
    "Multfilm": {"uz": "Multfilm", "ru": "Мультфильм", "en": "Cartoon"},
    "Multserial": {"uz": "Multserial", "ru": "Мультсериал", "en": "Cartoon series"},
    "Epizodli multfilm": {
        "uz": "Epizodli multfilm",
        "ru": "Мультфильм с эпизодами",
        "en": "Cartoon with episodes",
    },
    "Anime (film)": {"uz": "Anime (film)", "ru": "Аниме (фильм)", "en": "Anime (film)"},
    "Anime (serial)": {
        "uz": "Anime (serial)",
        "ru": "Аниме (сериал)",
        "en": "Anime (series)",
    },
    "Anime (mini)": {"uz": "Anime (mini)", "ru": "Аниме (мини)", "en": "Anime (mini)"},
}


async def _send_chunks(message, text: str, parse_mode: str = "HTML"):
    """4096 belgidan uzun xabarlarni bo'lib yuboradi (HTML teglar buzilmasligi uchun)."""
    MAX = 4096
    while len(text) > MAX:
        cut = text.rfind("\n\n", 0, MAX)
        if cut == -1:
            cut = MAX
        else:
            cut += 2
        await message.answer(text[:cut].strip(), parse_mode=parse_mode)
        text = text[cut:]
    if text.strip():
        await message.answer(text.strip(), parse_mode=parse_mode)


def _get_name_from_dict(name_obj, user_lang: str) -> str:
    """
    Dict yoki string bo'lishi mumkin bo'lgan name'dan
    foydalanuvchi tiliga mos qiymatni oladi.
    """
    if isinstance(name_obj, dict):
        # Foydalanuvchi tili → 'uz' → birinchi mavjud qiymat
        return (
            name_obj.get(user_lang)
            or name_obj.get("uz")
            or name_obj.get("ru")
            or name_obj.get("en")
            or next(
                (v for v in name_obj.values() if isinstance(v, str) and v.strip()), ""
            )
        )
    return str(name_obj) if name_obj else ""


# ─────────────────────────────────────────────
# FIX #4: IsGenreButton — Filter class (oddiy funksiya ishlamaydi)
# ─────────────────────────────────────────────


class IsGenreButton(Filter):
    async def __call__(self, message: Message) -> bool:
        text = message.text
        if not text:
            return False
        clean_text = text[2:] if text.startswith("✅ ") else text
        return any(clean_text == str(g["label"]) for g in GENRES)


# ─────────────────────────────────────────────
# FIX #3: VIP statusni bir joyda olish
# ─────────────────────────────────────────────


async def get_vip_status(session: AsyncSession, user_id: int) -> bool:
    from src.app.bot.common.utils import is_active_vip

    db_user = await UserActions(session).get_user(user_id)
    return await is_active_vip(db_user, session)


# ─────────────────────────────────────────────
# NAVIGATSIYA HANDLERLARI
# ─────────────────────────────────────────────


@movie_search_router.message(F.text == BTN_MOVIES)
async def cinema_category(message: Message):
    await message.answer(
        str(_("🎬 <b>Kino kategoriyasi</b>\n\nQaysi turdagi kontent kerak?")),
        reply_markup=get_cinema_menu(),
        parse_mode="HTML",
    )


@movie_search_router.message(F.text == BTN_ANIME)
async def anime_category(message: Message):
    await message.answer(
        str(_("🎌 <b>Anime kategoriyasi</b>\n\nQaysi turdagi anime kerak?")),
        reply_markup=get_anime_menu(),
        parse_mode="HTML",
    )


@movie_search_router.message(F.text == BTN_CARTOON)
async def cartoon_category(message: Message):
    await message.answer(
        str(_("🎨 <b>Multfilm kategoriyasi</b>\n\nQaysi turdagi multfilm kerak?")),
        reply_markup=get_cartoon_menu(),
        parse_mode="HTML",
    )


@movie_search_router.message(
    F.text.regexp(r"^(⬅️|🔙)\s*(Orqaga|Back|Назад)$") | (F.text == BTN_BACK)
)
async def back_to_main(message: Message):
    await message.answer(str(_("🏠 Asosiy menyu")), reply_markup=get_main_menu())


# ─────────────────────────────────────────────
# RANDOM FILM HANDLER
# ─────────────────────────────────────────────


@movie_search_router.message(
    F.text.in_(
        [
            BTN_RND_FILM,
            BTN_RND_SERIES,
            BTN_RND_MINI,
            BTN_RND_ANIME,
            BTN_RND_ANIME_SERIES,
            BTN_RND_ANIME_MINI,
            BTN_RND_CARTOON,
            BTN_RND_CARTOON_SERIES,
            BTN_RND_CARTOON_MINI,
        ]
    )
)
async def random_film_handler(message: Message, session: AsyncSession):
    random_movie = None
    actions = None
    text = message.text

    # --- KINO ---
    if text == BTN_RND_FILM:
        actions = FeatureFilmsActions(session)
        random_movie = await actions.get_random_feature_film()
    elif text == BTN_RND_SERIES:
        actions = SeriesActions(session)
        random_movie = await actions.get_random_series_first_episode()
    elif text == BTN_RND_MINI:
        actions = MiniSeriesActions(session)
        random_movie = await actions.get_random_mini_series_first_episode()

    # --- ANIME ---
    elif text == BTN_RND_ANIME:
        actions = AnimeFeatureActions(session)
        random_movie = await actions.get_random_feature_film()
    elif text == BTN_RND_ANIME_SERIES:
        actions = AnimeSeriesActions(session)
        random_movie = await actions.get_random_series_first_episode()
    elif text == BTN_RND_ANIME_MINI:
        actions = AnimeMiniSeriesActions(session)
        random_movie = await actions.get_random_mini_series_first_episode()

    # --- MULTFILM ---
    elif text == BTN_RND_CARTOON:
        actions = MultiFilmFeatureActions(session)
        random_movie = await actions.get_random_feature_film()
    elif text == BTN_RND_CARTOON_SERIES:
        actions = MultiFilmSeriesActions(session)
        random_movie = await actions.get_random_series_first_episode()
    elif text == BTN_RND_CARTOON_MINI:
        actions = MultiFilmMiniSeriesActions(session)
        random_movie = await actions.get_random_mini_series_first_episode()

    if not random_movie:
        await message.answer(str(_("😔 Hozircha bu turdagi kontent mavjud emas.")))
        return

    favorite_actions = FavoriteMoviesActions(session)
    saved = bool(
        await favorite_actions.get_favorites(random_movie.code, message.from_user.id)
    )
    user_lang = await get_user_language(message.from_user, session)
    is_vip = await get_vip_status(session, message.from_user.id)  # FIX #3

    (
        video_to_send,
        name,
        caption,
        target_language,
        target_quality,
        files,
        _unused,
        thumbnail_id,
    ) = resolve_movie_media(random_movie, user_lang, is_vip=is_vip)

    # FIX #2: lambda closure — local variable bilan capture
    _actions = actions
    _movie = random_movie

    if not video_to_send:
        # 1. Qo'lda tarjima
        prompts = {
            "uz": "💎 Bu filmni ko'rish uchun VIP obuna talab qilinadi",
            "ru": "💎 Для просмотра этого фильма требуется VIP-подписка",
            "en": "💎 VIP subscription is required to watch this movie",
        }
        prompt_text = prompts.get(user_lang, prompts["uz"])
        await message.answer(prompt_text)

        # 2. VIP menyuni chiqarish
        from src.app.bot.handlers.user.account import vip_tarif_handler

        await vip_tarif_handler(message, session=session)
        return

    if isinstance(random_movie, (FeatureFilm, MultiFilmFeature, AnimeFeature)):
        await message.answer_video(
            video=video_to_send,
            caption=caption,
            reply_markup=film_kbd(
                random_movie.code,
                saved,
                files=files,
                current_quality=target_quality,
                current_language=target_language,
                is_vip=is_vip,
            ),
            protect_content=not is_vip,
        )
        await track_and_increment_view(
            user_id=message.from_user.id,
            movie_code=_movie.code,
            increment_func=lambda: _actions.increment_views(_movie.code),
        )

    elif isinstance(random_movie, (MiniSeries, MultiFilmMiniSeries, AnimeMiniSeries)):
        ms_all = await actions.get_mini_series(random_movie.code)
        filtered_ms = [
            s
            for s in ms_all
            if (isinstance(s.files, dict) and target_language in s.files)
            or (
                isinstance(s.language, str)
                and target_language in (s.language or "").split(",")
            )
        ]
        if not filtered_ms:
            filtered_ms = ms_all
        serias_count = len(filtered_ms)

        if not video_to_send:
            prompts = {
                "uz": "💎 Bu filmni ko'rish uchun VIP obuna talab qilinadi",
                "ru": "💎 Для просмотра этого фильма требуется VIP-подписка",
                "en": "💎 VIP subscription is required to watch this movie",
            }
            prompt_text = prompts.get(user_lang, prompts["uz"])
            await message.answer(prompt_text)

            from src.app.bot.handlers.user.account import vip_tarif_handler
            await vip_tarif_handler(message, session=session)
            return

        await message.answer_video(
            video=video_to_send,
            caption=caption,
            reply_markup=mini_series_player_kbd(
                random_movie.code,
                random_movie.series,
                serias_count,
                saved,
                files=files,
                current_quality=target_quality,
                current_language=target_language,
                is_vip=is_vip,
            ),
            protect_content=not is_vip,
        )
        _series_num = _movie.series
        await track_and_increment_view(
            user_id=message.from_user.id,
            movie_code=_movie.code,
            increment_func=lambda: _actions.increment_views(_movie.code, _series_num),
        )

    elif isinstance(random_movie, (Series, MultiFilmSeries, AnimeSeries)):
        s_all = await actions.get_series(random_movie.code)
        filtered_s = [
            s
            for s in s_all
            if (isinstance(s.files, dict) and target_language in s.files)
            or (
                isinstance(s.language, str)
                and target_language in (s.language or "").split(",")
            )
        ]
        if not filtered_s:
            filtered_s = s_all

        current_season_series = sum(
            1 for s in filtered_s if s.season == random_movie.season
        )
        series_count = len(filtered_s)
        seasons_count = len(set(s.season for s in filtered_s)) if filtered_s else 0

        if not video_to_send:
            prompts = {
                "uz": "💎 Bu filmni ko'rish uchun VIP obuna talab qilinadi",
                "ru": "💎 Для просмотра этого фильма требуется VIP-подписка",
                "en": "💎 VIP subscription is required to watch this movie",
            }
            prompt_text = prompts.get(user_lang, prompts["uz"])
            await message.answer(prompt_text)

            from src.app.bot.handlers.user.account import vip_tarif_handler
            await vip_tarif_handler(message, session=session)
            return

        await message.answer_video(
            video=video_to_send,
            caption=caption,
            reply_markup=series_player_kbd(
                random_movie.code,
                1,
                series_count,
                random_movie.season,
                seasons_count,
                random_movie.series,
                current_season_series,
                saved,
                files=files,
                current_quality=target_quality,
                current_language=target_language,
                is_vip=is_vip,
            ),
            protect_content=not is_vip,
        )
        _season = _movie.season
        _series = _movie.series
        await track_and_increment_view(
            user_id=message.from_user.id,
            movie_code=_movie.code,
            increment_func=lambda: _actions.increment_views(
                _movie.code, _season, _series
            ),
        )


# ─────────────────────────────────────────────
# TOP FILMS HANDLER
# ─────────────────────────────────────────────


@movie_search_router.message(
    F.text.in_([BTN_TOP_MOVIES, BTN_TOP_ANIME, BTN_TOP_CARTOON])
)
async def top_films_handler(message: Message, session: AsyncSession):
    text = message.text
    category = "all"

    if text == BTN_TOP_MOVIES:
        category = "cinema"
    elif text == BTN_TOP_ANIME:
        category = "anime"
    elif text == BTN_TOP_CARTOON:
        category = "cartoon"

    await send_top_movies(message, session, interval="total", category=category)


async def send_top_movies(
    message,
    session,
    interval: str = "total",
    category: str = "all",
):
    import logging

    from src.app.bot.common.i18n import i18n
    from src.app.bot.common.utils import get_user_language
    from src.app.database.queries.movie.top_movies import TopMoviesActions

    logger = logging.getLogger(__name__)
    _ = i18n.gettext

    try:
        top_movies_actions = TopMoviesActions(session)
        top_20 = await top_movies_actions.get_top_movies(
            interval=interval, limit=20, category=category
        )
    except Exception as e:
        logger.error("Error getting top movies: %s", e)
        await message.answer(
            str(_("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring."))
        )
        return

    cat_names = {
        "all": "",
        "cinema": str(_("KINO")),
        "anime": str(_("ANIME")),
        "cartoon": str(_("MULTFILM")),
    }
    cat_title = cat_names.get(category, "")
    text = str(_("🔥 {category} TOP 20 FILMLAR:\n\n")).format(category=cat_title)

    if not top_20:
        text += str(_("Hozircha ma'lumotlar yo'q."))
    else:
        user_lang = await get_user_language(message.from_user, session)
        for index, m in enumerate(top_20, start=1):
            name = _get_name_from_dict(m["name"], user_lang)
            # ✅ Kontent turini foydalanuvchi tiliga qarab tarjima qilish
            type_label = TYPE_TRANSLATIONS.get(m["type"], {}).get(user_lang, m["type"])
            text += (
                f"<b>{index}</b>. <b>{name}</b>\n"
                f"   ├─ <b>{str(_('Turi'))}</b>: <b>{type_label}</b>\n"
                f"   ├─ <b>{str(_('Kod'))}</b>: <code>{m['code']}</code>\n"
                f"   ├─ <b>{str(_('Saqlangan'))}</b>: <b>{m['favs']}</b>\n"
                f"   └─ <b>{str(_('Ko\'rilgan'))}</b>: <b>{m['views']}</b>\n\n"
            )

    # ✅ Uzun xabarlarni bo'lib yuborish (Telegram 4096 belgi cheklovi)
    await _send_chunks(message, str(text))


# ─────────────────────────────────────────────
# GENRE KEYBOARD
# ─────────────────────────────────────────────


def get_genre_reply_keyboard(selected_genres: list[str]) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=str(_("🔍 Qidirish"))), KeyboardButton(text=str(BTN_BACK))
    )
    genre_buttons = []
    for g in GENRES:
        name = g["name"]
        checkmark = "✅ " if name in selected_genres else ""
        genre_buttons.append(KeyboardButton(text=f"{checkmark}{str(g['label'])}"))
    builder.add(*genre_buttons)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


# ─────────────────────────────────────────────
# GENRE HANDLERS
# ─────────────────────────────────────────────


@movie_search_router.message(
    F.text.in_([BTN_GENRE_MOVIES, BTN_GENRE_ANIME, BTN_GENRE_CARTOON])
)
async def movies_by_genre(message: Message, state: FSMContext):
    text = message.text
    category = "all"

    if text == BTN_GENRE_MOVIES:
        category = "cinema"
    elif text == BTN_GENRE_ANIME:
        category = "anime"
    elif text == BTN_GENRE_CARTOON:
        category = "cartoon"

    await state.set_state(SearchByGenreSG.select_genres)
    await state.update_data(selected_genres=[], category=category)

    cat_names = {
        "all": "",
        "cinema": str(_("KINO")),
        "anime": str(_("ANIME")),
        "cartoon": str(_("MULTFILM")),
    }
    cat_title = cat_names.get(category, "")

    await message.answer(
        str(
            _(
                "🎭 <b>{category} Janrlarni tanlang:</b>\n\n"
                "Bir nechta tanlashingiz mumkin. Tanlab bo'lgach <b>🔍 Qidirish</b> tugmasini bosing."
            )
        ).format(category=cat_title),
        reply_markup=get_genre_reply_keyboard([]),
        parse_mode="HTML",
    )


@movie_search_router.message(
    SearchByGenreSG.select_genres,
    F.text.regexp(r"^(⬅️|🔙)\s*(Orqaga|Back|Назад)$") | (F.text == str(BTN_BACK)),
)
async def genre_search_back(message: Message, state: FSMContext):
    data = await state.get_data()
    category = data.get("category", "all")
    await state.clear()

    if category == "cinema":
        markup = get_cinema_menu()
        text = str(_("🎬 Kino bo'limi"))
    elif category == "anime":
        markup = get_anime_menu()
        text = str(_("🎌 Anime bo'limi"))
    elif category == "cartoon":
        markup = get_cartoon_menu()
        text = str(_("🎨 Multfilm bo'limi"))
    else:
        markup = get_main_menu()
        text = str(_("🏠 Asosiy menyu"))

    await message.answer(text, reply_markup=markup)


@movie_search_router.message(
    SearchByGenreSG.select_genres,
    F.text.regexp(r"^(🔍|🔎)\s*(Qidirish|Search|Поиск)$")
    | (F.text == _("🔍 Qidirish")),
)
async def genre_search_execute(message, state, session):
    from src.app.bot.common.genres import GENRES, get_genre_display_text
    from src.app.bot.common.i18n import i18n
    from src.app.bot.common.utils import get_user_language
    from src.app.bot.keyboards.replay import (
        get_anime_menu,
        get_cartoon_menu,
        get_cinema_menu,
        get_main_menu,
    )
    from src.app.database.queries.movie.top_movies import TopMoviesActions

    _ = i18n.gettext

    data = await state.get_data()
    selected = data.get("selected_genres", [])
    category = data.get("category", "all")

    if not selected:
        await message.answer(str(_("⚠️ Kamida bitta janrni tanlang!")))
        return

    # Genre nomlarini barcha variantlar bilan kengaytirish
    # Lekin asosiy qidiruv uchun faqat texnik nomlar (g["name"]) yetarli
    # chunki DB da genres "Drama", "Comedy" kabi saqlangan
    genre_names = list(selected)  # texnik nomlar (ruscha, masalan "🎭 Драма")

    top_actions = TopMoviesActions(session)
    results = await top_actions.get_top_by_genres(
        genre_names, limit=10, category=category
    )

    genre_header = get_genre_display_text(selected)
    cat_names = {
        "all": "",
        "cinema": str(_("KINO")),
        "anime": str(_("ANIME")),
        "cartoon": str(_("MULTFILM")),
    }
    cat_title = cat_names.get(category, "")

    text = str(_("🎭 {category} Janrlar bo'yicha qidiruv\n\n")).format(
        category=cat_title
    )
    text += str(_("🔍 <b>Janrlar:</b> {genres}\n\n")).format(genres=genre_header)

    if results:
        text += str(_("<b>Top 10 ta mos filmlar:</b>\n\n"))
        user_lang = await get_user_language(message.from_user, session)
        for index, m in enumerate(results, start=1):
            name = _get_name_from_dict(m["name"], user_lang)
            # ✅ Kontent turini foydalanuvchi tiliga qarab tarjima qilish
            type_label = TYPE_TRANSLATIONS.get(m["type"], {}).get(user_lang, m["type"])
            text += (
                f"<b>{index}. {name}</b>\n"
                f"   ├─ <b>{str(_('Turi'))}</b>: <b>{type_label}</b>\n"
                f"   ├─ <b>{str(_('Kod'))}</b>: <code>{m['code']}</code>\n"
                f"   ├─ <b>{str(_('Saqlangan'))}</b>: <b>{m['favs']}</b>\n"
                f"   └─ <b>{str(_('Ko\'rilgan'))}</b>: <b>{m['views']}</b>\n\n"
            )
        text += str(_("<b>Ko'rish uchun film kodini yuboring.</b>"))
    else:
        text += str(_("Hozircha ma'lumotlar yo'q."))

    # ✅ Uzun xabarlarni bo'lib yuborish
    await _send_chunks(message, text)


# FIX #4: IsGenreButton() Filter class ishlatilmoqda
@movie_search_router.message(SearchByGenreSG.select_genres, IsGenreButton())
async def genre_search_toggle(message: Message, state: FSMContext):
    text = message.text
    clean_text = text[2:] if text.startswith("✅ ") else text

    data = await state.get_data()
    selected = list(data.get("selected_genres", []))

    target_genre = None
    for g in GENRES:
        if clean_text == str(g["label"]):
            target_genre = g["name"]
            break

    if target_genre:
        if target_genre in selected:
            selected.remove(target_genre)
        else:
            selected.append(target_genre)

    await state.update_data(selected_genres=selected)

    selected_display = get_genre_display_text(selected)
    await message.answer(
        str(_("🎭 <b>Tanlangan janrlar:</b> {genres}")).format(genres=selected_display),
        reply_markup=get_genre_reply_keyboard(selected),
        parse_mode="HTML",
    )


# ─────────────────────────────────────────────
# ASOSIY QIDIRUV HANDLER
# ─────────────────────────────────────────────


@movie_search_router.message(F.text & ~F.text.startswith("/"))
async def movie_search_handler(message: Message, session: AsyncSession):
    if message.text in [
        str(BTN_BACK),
        str(BTN_MOVIES),
        str(BTN_ANIME),
        str(BTN_CARTOON),
        str(BTN_FAVORITES),
    ]:
        return

    query = message.text.strip()

    if query.isdigit():
        code = int(query)
        found_movie = None
        actions = None

        # --- KINO ---
        actions_f = FeatureFilmsActions(session)
        actions_ms = MiniSeriesActions(session)
        actions_s = SeriesActions(session)

        found_movie = await actions_f.get_feature_film(code)
        if found_movie:
            actions = actions_f
        else:
            found_movie = await actions_ms.get_mini_series(code)
            if found_movie:
                actions = actions_ms
            else:
                found_movie = await actions_s.get_series(code)
                if found_movie:
                    actions = actions_s

        # --- MULTFILM ---
        if not found_movie:
            actions_f = MultiFilmFeatureActions(session)
            actions_ms = MultiFilmMiniSeriesActions(session)
            actions_s = MultiFilmSeriesActions(session)

            found_movie = await actions_f.get_feature_film(code)
            if found_movie:
                actions = actions_f
            else:
                found_movie = await actions_ms.get_mini_series(code)
                if found_movie:
                    actions = actions_ms
                else:
                    found_movie = await actions_s.get_series(code)
                    if found_movie:
                        actions = actions_s

        # --- ANIME ---
        if not found_movie:
            actions_f = AnimeFeatureActions(session)
            actions_ms = AnimeMiniSeriesActions(session)
            actions_s = AnimeSeriesActions(session)

            found_movie = await actions_f.get_feature_film(code)
            if found_movie:
                actions = actions_f
            else:
                found_movie = await actions_ms.get_mini_series(code)
                if found_movie:
                    actions = actions_ms
                else:
                    found_movie = await actions_s.get_series(code)
                    if found_movie:
                        actions = actions_s

        if not found_movie:
            await message.answer(
                str(
                    _(
                        "😔 Hechnima topilmadi.\n\nKiritilgan kod bo'yicha film topilmadi va shu nomdagi film ham yo'q."
                    )
                ),
                reply_markup=get_instagram_channel_kbd(),
            )
            return

        favorite_actions = FavoriteMoviesActions(session)
        saved = bool(await favorite_actions.get_favorites(code, message.from_user.id))
        user_lang = await get_user_language(message.from_user, session)
        is_vip = await get_vip_status(session, message.from_user.id)  # FIX #3

        # FIX #1: FeatureFilm — bitta object
        if isinstance(found_movie, (FeatureFilm, MultiFilmFeature, AnimeFeature)):
            (
                video_to_send,
                name,
                caption,
                target_language,
                target_quality,
                files,
                _captions,
                thumbnail_id,
            ) = resolve_movie_media(found_movie, user_lang, is_vip=is_vip)

            if not video_to_send:
                prompts = {
                    "uz": "💎 Bu filmni ko'rish uchun VIP obuna talab qilinadi",
                    "ru": "💎 Для просмотра этого фильма требуется VIP-подписка",
                    "en": "💎 VIP subscription is required to watch this movie",
                }
                prompt_text = prompts.get(user_lang, prompts["uz"])
                await message.answer(prompt_text)

                from src.app.bot.handlers.user.account import vip_tarif_handler
                await vip_tarif_handler(message, session=session)
                return

            await message.answer_video(
                video=video_to_send,
                caption=caption,
                reply_markup=film_kbd(
                    code,
                    saved,
                    files=files,
                    current_quality=target_quality,
                    current_language=target_language,
                    is_vip=is_vip,
                ),
                protect_content=not is_vip,
            )
            # FIX #2: closure
            _actions, _code = actions, code
            await track_and_increment_view(
                user_id=message.from_user.id,
                movie_code=_code,
                increment_func=lambda: _actions.increment_views(_code),
            )
            return

        # FIX #1: MiniSeries — list qaytaradi
        elif (
            isinstance(found_movie, list)
            and found_movie
            and isinstance(
                found_movie[0], (MiniSeries, MultiFilmMiniSeries, AnimeMiniSeries)
            )
        ):
            ms = found_movie
            (
                video_to_send,
                name,
                caption,
                target_language,
                target_quality,
                files,
                _captions,
                thumbnail_id,
            ) = resolve_movie_media(ms[0], user_lang, is_vip=is_vip)

            filtered_ms = [
                s
                for s in ms
                if (isinstance(s.files, dict) and target_language in s.files)
                or (
                    isinstance(s.language, str)
                    and target_language in (s.language or "").split(",")
                )
            ]
            if not filtered_ms:
                filtered_ms = ms
            serias_count = len(filtered_ms)

            if not video_to_send:
                prompts = {
                    "uz": "💎 Bu filmni ko'rish uchun VIP obuna talab qilinadi",
                    "ru": "💎 Для просмотра этого фильма требуется VIP-подписка",
                    "en": "💎 VIP subscription is required to watch this movie",
                }
                prompt_text = prompts.get(user_lang, prompts["uz"])
                await message.answer(prompt_text)

                from src.app.bot.handlers.user.account import vip_tarif_handler
                await vip_tarif_handler(message, session=session)
                return

            await message.answer_video(
                video=video_to_send,
                caption=caption,
                reply_markup=mini_series_player_kbd(
                    code,
                    1,
                    serias_count,
                    saved,
                    files=files,
                    current_quality=target_quality,
                    current_language=target_language,
                    is_vip=is_vip,
                ),
                protect_content=not is_vip,
            )
            # FIX #2: closure
            _actions, _code = actions, code
            await track_and_increment_view(
                user_id=message.from_user.id,
                movie_code=_code,
                increment_func=lambda: _actions.increment_views(_code, 1),
            )
            return

        # FIX #1: Series — list qaytaradi
        elif (
            isinstance(found_movie, list)
            and found_movie
            and isinstance(found_movie[0], (Series, MultiFilmSeries, AnimeSeries))
        ):
            series = found_movie
            first_ep = series[0]
            (
                video_to_send,
                name,
                caption,
                target_language,
                target_quality,
                files,
                _captions,
                thumbnail_id,
            ) = resolve_movie_media(first_ep, user_lang, is_vip=is_vip)

            filtered_s = [
                s
                for s in series
                if (isinstance(s.files, dict) and target_language in s.files)
                or (
                    isinstance(s.language, str)
                    and target_language in (s.language or "").split(",")
                )
            ]
            if not filtered_s:
                filtered_s = series

            current_season_series = sum(
                1 for s in filtered_s if s.season == first_ep.season
            )
            series_count = len(filtered_s)
            seasons_count = len(set(s.season for s in filtered_s)) if filtered_s else 0

            if not video_to_send:
                prompts = {
                    "uz": "💎 Bu filmni ko'rish uchun VIP obuna talab qilinadi",
                    "ru": "💎 Для просмотра этого фильма требуется VIP-подписка",
                    "en": "💎 VIP subscription is required to watch this movie",
                }
                prompt_text = prompts.get(user_lang, prompts["uz"])
                await message.answer(prompt_text)

                from src.app.bot.handlers.user.account import vip_tarif_handler
                await vip_tarif_handler(message, session=session)
                return

            await message.answer_video(
                video=video_to_send,
                caption=caption,
                reply_markup=series_player_kbd(
                    code,
                    1,
                    series_count,
                    first_ep.season,
                    seasons_count,
                    first_ep.series,
                    current_season_series,
                    saved,
                    files=files,
                    current_quality=target_quality,
                    current_language=target_language,
                    is_vip=is_vip,
                ),
                protect_content=not is_vip,
            )
            # FIX #2: closure
            _actions, _code = actions, code
            _season, _series = first_ep.season, first_ep.series
            await track_and_increment_view(
                user_id=message.from_user.id,
                movie_code=_code,
                increment_func=lambda: _actions.increment_views(
                    _code, _season, _series
                ),
            )
            return

    # ─── MATN QIDIRUV ───
    search_engine = SearchRepository(session)
    results = []
    user_lang = await get_user_language(message.from_user, session)

    def get_search_item_text(obj, icon: str) -> str:
        display_name = get_localized_name(obj, user_lang)
        genres_text = get_genre_display_text(deserialize_genres(obj.genres))
        return (
            f"{icon} <b>{display_name}</b>\n"
            f"└ 🎭 {str(_('Janr'))}: <b>{genres_text}</b>\n"
            f"└ 🆔 {str(_('Kod'))}: <code>{obj.code}</code>\n"
        )

    query_lower = message.text.lower()

    for obj, score in await search_engine.search_feature_films(query_lower):
        results.append(get_search_item_text(obj, "🎬"))
    for obj, score in await search_engine.search_series(query_lower):
        results.append(get_search_item_text(obj, "📺"))
    for obj, score in await search_engine.search_mini_series(query_lower):
        results.append(get_search_item_text(obj, "🧩"))

    if not results:
        await message.answer(
            str(
                _(
                    "😔 Kechirasiz, bu nomdagi film topilmadi.\n\n"
                    "Nomini to'g'ri yozganingizni tekshiring yoki kod orqali qidiring."
                )
            ),
            reply_markup=get_instagram_channel_kbd(),
        )
    else:
        max_result = 20
        shown_results = results[:max_result]
        response_text = str(_("🔍 <b>Qidiruv natijalari:</b>\n\n")) + "\n".join(
            shown_results
        )

        if len(results) > max_result:
            response_text += str(
                _("\n\n<i>... va yana {count} ta natija. Aniqroq qidiring.</i>")
            ).format(count=len(results) - max_result)

        response_text += str(
            _("\n\n<b>Ko'rish uchun kerakli filmni kodini yuboring.</b>")
        )
        await message.answer(str(response_text), parse_mode="HTML")


# ─────────────────────────────────────────────
# VIEW TRACKER
# ─────────────────────────────────────────────


async def track_and_increment_view(
    user_id: int,
    movie_code: int,
    increment_func,
):
    try:
        settings = load_config()
        if await ViewTracker.is_new_view(settings.redis_url, user_id, movie_code):
            await increment_func()
    except Exception as e:
        logger.error(f"Error tracking view: {e}")
