from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
import logging
import html
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.common.i18n import lazy_gettext as _

from src.app.database.queries.movie.favorite_movies import FavoriteMoviesActions
from src.app.database.queries.movie.feature_films import FeatureFilmsActions
from src.app.database.queries.movie.mini_series import MiniSeriesActions
from src.app.database.queries.movie.series import SeriesActions
from src.app.database.queries.movie.multi_films import MultiFilmFeatureActions, MultiFilmSeriesActions, MultiFilmMiniSeriesActions
from src.app.database.queries.movie.anime import AnimeFeatureActions, AnimeSeriesActions, AnimeMiniSeriesActions
from src.app.bot.common.buttons import BTN_FAVORITES
from src.app.bot.common.utils import get_user_language, get_localized_name

logger = logging.getLogger(__name__)
favorite_movies_router = Router()

@favorite_movies_router.message(Command("favorites"))
@favorite_movies_router.message(F.text == BTN_FAVORITES)
async def list_favorite_movies(message: Message, session: AsyncSession):
    try:
        user_lang = await get_user_language(message.from_user, session)
        favorites_actions = FavoriteMoviesActions(session)
        favorite_films_data = await favorites_actions.get_all_favorites_by_user_id(user_id=message.from_user.id)

        if not favorite_films_data:
            await message.answer(str(_("😔 <b>Siz hali hech nima saqlamagansiz</b>")), parse_mode="HTML")
            return

        texts = str(_("📬 <b>Sizning filmlar to'plamingiz</b>\n"))
        texts += "━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Action guruhlari
        cinema_actions = [
            (FeatureFilmsActions(session), "🎥"),
            (SeriesActions(session), "📺"),
            (MiniSeriesActions(session), "🎞️"),
        ]
        
        anime_actions = [
            (AnimeFeatureActions(session), "🎥"),
            (AnimeSeriesActions(session), "📺"),
            (AnimeMiniSeriesActions(session), "🎞️"),
        ]
        
        cartoon_actions = [
            (MultiFilmFeatureActions(session), "🎥"),
            (MultiFilmSeriesActions(session), "📺"),
            (MultiFilmMiniSeriesActions(session), "🎞️"),
        ]

        cinema_list = []
        anime_list = []
        cartoon_list = []

        for favorite_film_data in favorite_films_data:
            movie_code = favorite_film_data.movie_code
            found = False
            
            # 1. Kinodan qidirish
            for actions, icon in cinema_actions:
                obj = None
                if isinstance(actions, FeatureFilmsActions):
                    obj = await actions.get_feature_film(movie_code)
                elif isinstance(actions, SeriesActions):
                    res = await actions.get_series(movie_code)
                    obj = res[0] if res else None
                elif isinstance(actions, MiniSeriesActions):
                    res = await actions.get_mini_series(movie_code)
                    obj = res[0] if res else None
                
                if obj:
                    display_name = get_localized_name(obj, user_lang)
                    cinema_list.append(_("{icon} <b>{name}</b>\n└ 🆔 Kod: <code>{code}</code>").format(icon=icon, name=html.escape(display_name), code=movie_code))
                    found = True
                    break
            
            if found: continue

            # 2. Animedan qidirish
            for actions, icon in anime_actions:
                obj = None
                if isinstance(actions, AnimeFeatureActions):
                    obj = await actions.get_feature_film(movie_code)
                elif isinstance(actions, AnimeSeriesActions):
                    res = await actions.get_series(movie_code)
                    obj = res[0] if res else None
                elif isinstance(actions, AnimeMiniSeriesActions):
                    res = await actions.get_mini_series(movie_code)
                    obj = res[0] if res else None
                
                if obj:
                    display_name = get_localized_name(obj, user_lang)
                    anime_list.append(_("{icon} <b>{name}</b>\n└ 🆔 Kod: <code>{code}</code>").format(icon=icon, name=html.escape(display_name), code=movie_code))
                    found = True
                    break

            if found: continue

            # 3. Multfilmdan qidirish
            for actions, icon in cartoon_actions:
                obj = None
                if isinstance(actions, MultiFilmFeatureActions):
                    obj = await actions.get_feature_film(movie_code)
                elif isinstance(actions, MultiFilmSeriesActions):
                    res = await actions.get_series(movie_code)
                    obj = res[0] if res else None
                elif isinstance(actions, MultiFilmMiniSeriesActions):
                    res = await actions.get_mini_series(movie_code)
                    obj = res[0] if res else None
                
                if obj:
                    display_name = get_localized_name(obj, user_lang)
                    cartoon_list.append(_("{icon} <b>{name}</b>\n└ 🆔 Kod: <code>{code}</code>").format(icon=icon, name=html.escape(display_name), code=movie_code))
                    found = True
                    break

        # Natijalarni birlashtirish
        if cinema_list:
            texts += str(_("🎬 <b>KINO VA SERIALAR:</b>\n"))
            texts += "\n\n".join(cinema_list)
            texts += "\n\n"
            
        if anime_list:
            texts += str(_("🎌 <b>ANIME:</b>\n"))
            texts += "\n\n".join(anime_list)
            texts += "\n\n"
            
        if cartoon_list:
            texts += str(_("🎨 <b>MULTFILM:</b>\n"))
            texts += "\n\n".join(cartoon_list)
            texts += "\n\n"

        texts += "━━━━━━━━━━━━━━━━━━━━━\n"
        texts += str(_("<i>Filmni ko'rish uchun uning kodini botga yuboring.</i>"))

        await message.answer(str(texts), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in list_favorite_movies: {e}")
        await message.answer(_("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring."))
