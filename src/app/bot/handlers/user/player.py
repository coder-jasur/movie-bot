from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InputMediaVideo
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.bot.common.i18n import lazy_gettext as _
from src.app.bot.keyboards.callback_data import (
    ActionType,
    FeatureFilmPlayerCD,
    MiniSeriesPlayerCD,
    SeriesPlayerCD,
)
from src.app.bot.keyboards.inline import (
    film_kbd,
    mini_series_player_kbd,
    series_player_kbd,
)
from src.app.database.queries.movie.anime import (
    AnimeMiniSeriesActions,
    AnimeSeriesActions,
)
from src.app.database.queries.movie.favorite_movies import FavoriteMoviesActions
from src.app.database.queries.movie.mini_series import MiniSeriesActions
from src.app.database.queries.movie.multi_films import (
    MultiFilmMiniSeriesActions,
    MultiFilmSeriesActions,
)
from src.app.database.queries.movie.series import SeriesActions

player_router = Router()


@player_router.callback_query(F.data == "close")
async def clouuse_window(call: CallbackQuery):
    await call.message.delete()


@player_router.callback_query(SeriesPlayerCD.filter())
async def series_player(
    call: CallbackQuery, session: AsyncSession, callback_data: SeriesPlayerCD
):
    from src.app.database.queries.user import UserActions

    user_actions = UserActions(session)
    db_user = await user_actions.get_user(call.from_user.id)

    from src.app.bot.common.utils import is_active_vip

    is_vip = await is_active_vip(db_user, session)

    bot_info = await call.bot.get_me()
    bot_username = bot_info.username

    favorites_actions = FavoriteMoviesActions(session)
    code = callback_data.code

    # Identify actions based on category search
    actions = None
    series_data = await SeriesActions(session).get_series(code)
    if series_data:
        actions = SeriesActions(session)
    if not actions:
        series_data = await MultiFilmSeriesActions(session).get_series(code)
        if series_data:
            actions = MultiFilmSeriesActions(session)
    if not actions:
        series_data = await AnimeSeriesActions(session).get_series(code)
        if series_data:
            actions = AnimeSeriesActions(session)

    if not actions:
        await call.answer(str(_("❌ Serial topilmadi")), show_alert=True)
        return

    from src.app.bot.common.utils import (
        get_user_language,
        resolve_movie_media,
    )

    user_lang = await get_user_language(call.from_user, session)
    target_language_req = callback_data.language or user_lang

    # Filter data based on selected language
    # Only keep episodes that have the requested language track
    filtered_series_data = [
        s
        for s in series_data
        if (isinstance(s.files, dict) and target_language_req in s.files)
        or (
            isinstance(s.language, str)
            and target_language_req in (s.language or "").split(",")
        )
    ]

    # If no episodes found for requested language, fallback to all series data to avoid crash
    # But usually resolve_movie_media handles this. Here we need it for counts.
    if not filtered_series_data:
        filtered_series_data = series_data

    current_series = next(
        (
            s
            for s in filtered_series_data
            if s.season == callback_data.season_number
            and s.series == callback_data.series_number
        ),
        None,
    )

    if current_series is None:
        # If specific episode not found in filtered data, maybe it doesn't exist in this language
        await call.answer(str(_("❌ Bu tilda ushbu qism mavjud emas")), show_alert=True)
        return

    current_index = next(
        (
            i
            for i, s in enumerate(filtered_series_data, start=1)
            if s.season == callback_data.season_number
            and s.series == callback_data.series_number
        ),
        1,
    )

    series_count_for_current_season = sum(
        1 for s in filtered_series_data if s.season == callback_data.season_number
    )
    series_count = len(filtered_series_data)
    seasons_count = (
        len(set(s.season for s in filtered_series_data)) if filtered_series_data else 0
    )

    user_id = call.from_user.id
    saved = await favorites_actions.get_favorites(callback_data.code, user_id)

    if callback_data.action == "save_to_favorites":
        await favorites_actions.add_favorite_movie(callback_data.code, user_id)
        saved = True
    elif callback_data.action == "remove_in_favorites":
        await favorites_actions.delete_favorite_movie(callback_data.code, user_id)
        saved = False

    if (
        callback_data.action == ActionType.set_quality
        and not is_vip
        and callback_data.quality in ["720p", "1080p"]
    ):
        from src.app.bot.handlers.user.account import vip_tarif_handler

        await call.answer(str(_("💎 VIP obuna talab qilinadi")), show_alert=False)
        await vip_tarif_handler(call.message)
        return

    (
        file_id,
        name,
        caption,
        target_language_res,
        target_quality,
        files,
        _captions,
        thumbnail_id,
    ) = resolve_movie_media(
        current_series, target_language_req, callback_data.quality, is_vip=is_vip
    )

    # If no sub-480p quality available for non-VIP, show VIP prompt
    if not is_vip and target_quality is None:
        from src.app.bot.handlers.user.account import vip_tarif_handler

        await call.answer(str(_("💎 Bu filmni ko'rish uchun VIP obuna talab qilinadi")), show_alert=True)
        await vip_tarif_handler(call.message)
        return

    show_quality_menu = callback_data.action == ActionType.open_quality_menu
    show_language_menu = callback_data.action == ActionType.open_language_menu

    if callback_data.action == ActionType.open_series_menu:
        from src.app.bot.keyboards.inline import _build_series_list_menu

        with suppress(TelegramBadRequest):
            await call.message.edit_reply_markup(
                reply_markup=_build_series_list_menu(
                    serias_count=series_count_for_current_season,
                    current_seria=callback_data.series_number,
                    cd_builder=lambda s: SeriesPlayerCD(
                        code=code,
                        series_number=s,
                        season_number=callback_data.season_number,
                        all_series_numebr=current_series.series,
                        action=(
                            ActionType.next_series
                            if s > callback_data.series_number
                            else ActionType.back_series
                        ),
                        quality=target_quality,
                        language=target_language_res,
                    ).pack(),
                    back_action=True,
                )
            )
        return

    if callback_data.action == ActionType.open_seasons_menu:
        from src.app.bot.keyboards.inline import _build_seasons_list_menu

        with suppress(TelegramBadRequest):
            await call.message.edit_reply_markup(
                reply_markup=_build_seasons_list_menu(
                    seasons_count=seasons_count,
                    current_season=callback_data.season_number,
                    cd_builder=lambda s: SeriesPlayerCD(
                        code=code,
                        series_number=1,
                        season_number=s,
                        all_series_numebr=current_series.series,
                        action=(
                            ActionType.next_season
                            if s > callback_data.season_number
                            else ActionType.back_season
                        ),
                        quality=target_quality,
                        language=target_language_res,
                    ).pack(),
                    back_action=True,
                )
            )
        return

    if callback_data.action in [
        ActionType.open_quality_menu,
        ActionType.close_quality_menu,
        ActionType.open_language_menu,
        "save_to_favorites",
        "remove_in_favorites",
    ]:
        with suppress(TelegramBadRequest):
            await call.message.edit_reply_markup(
                reply_markup=series_player_kbd(
                    code=callback_data.code,
                    current_series=current_index,
                    series_count=series_count,
                    current_season=callback_data.season_number,
                    seasons_count=seasons_count,
                    current_series_for_current_season=callback_data.series_number,
                    series_count_for_current_season=series_count_for_current_season,
                    saved=bool(saved),
                    bot_username=bot_username,
                    files=files,
                    current_quality=target_quality,
                    current_language=target_language_res,
                    show_quality_menu=show_quality_menu,
                    show_language_menu=show_language_menu,
                    is_vip=is_vip,
                )
            )
        return

    with suppress(TelegramBadRequest):
        await call.message.edit_media(
            InputMediaVideo(media=file_id, caption=caption),
            reply_markup=series_player_kbd(
                code=callback_data.code,
                current_series=current_index,
                series_count=series_count,
                current_season=callback_data.season_number,
                seasons_count=seasons_count,
                current_series_for_current_season=callback_data.series_number,
                series_count_for_current_season=series_count_for_current_season,
                saved=bool(saved),
                bot_username=bot_username,
                files=files,
                current_quality=target_quality,
                current_language=target_language_res,
                show_quality_menu=False,
                show_language_menu=False,
                is_vip=is_vip,
            ),
        )


@player_router.callback_query(FeatureFilmPlayerCD.filter())
async def feature_movies_player(
    call: CallbackQuery, callback_data: FeatureFilmPlayerCD, session: AsyncSession
):
    favorite_films_actions = FavoriteMoviesActions(session)

    from src.app.database.queries.user import UserActions

    user_actions = UserActions(session)
    db_user = await user_actions.get_user(call.from_user.id)

    from src.app.bot.common.utils import is_active_vip

    is_vip = await is_active_vip(db_user, session)

    bot_info = await call.bot.get_me()
    bot_username = bot_info.username

    saved = await favorite_films_actions.get_favorites(
        callback_data.code, call.from_user.id
    )
    saved = True if saved else False

    if callback_data.actions == "delete_for_favorites" and saved:
        await favorite_films_actions.delete_favorite_movie(
            callback_data.code, call.from_user.id
        )
        saved = False
        await call.answer(str(_("❌ Film sevimlilardan o‘chirildi")))

    elif callback_data.actions == "add_to_favorites" and not saved:
        await favorite_films_actions.add_favorite_movie(
            callback_data.code, call.from_user.id
        )
        saved = True
        await call.answer(str(_("💾 Film sevimlilarga qo‘shildi")))

    saved = bool(saved)

    # Quality Selection & Main Logic
    from src.app.database.queries.movie.anime import AnimeFeatureActions
    from src.app.database.queries.movie.feature_films import FeatureFilmsActions
    from src.app.database.queries.movie.multi_films import MultiFilmFeatureActions

    actions = FeatureFilmsActions(session)
    movie = await actions.get_feature_film(callback_data.code)
    if not movie:
        movie = await MultiFilmFeatureActions(session).get_feature_film(
            callback_data.code
        )
    if not movie:
        movie = await AnimeFeatureActions(session).get_feature_film(callback_data.code)

    if not movie:
        await call.answer(str(_("❌ Film topilmadi")), show_alert=True)
        return

    from src.app.bot.common.utils import (
        get_user_language,
        resolve_movie_media,
    )

    user_lang = await get_user_language(call.from_user, session)

    target_language_req = callback_data.language or user_lang
    if (
        callback_data.actions == ActionType.set_quality
        and not is_vip
        and callback_data.quality in ["480p", "720p", "1080p"]
    ):
        from src.app.bot.handlers.user.account import vip_tarif_handler

        await call.answer(str(_("💎 VIP obuna talab qilinadi")), show_alert=False)
        await vip_tarif_handler(call.message)
        return

    (
        file_id,
        name,
        caption,
        target_language_res,
        target_quality,
        files,
        _captions,
        thumbnail_id,
    ) = resolve_movie_media(
        movie, target_language_req, callback_data.quality, is_vip=is_vip
    )

    # If no sub-480p quality available for non-VIP, show VIP prompt
    if not is_vip and target_quality is None:
        from src.app.bot.handlers.user.account import vip_tarif_handler

        await call.answer(str(_("💎 Bu filmni ko'rish uchun VIP obuna talab qilinadi")), show_alert=True)
        await vip_tarif_handler(call.message)
        return

    # files is now the parsed dictionary

    show_quality_menu = callback_data.actions == ActionType.open_quality_menu
    show_language_menu = callback_data.actions == ActionType.open_language_menu

    if callback_data.actions in [
        ActionType.open_quality_menu,
        ActionType.close_quality_menu,
        ActionType.open_language_menu,
        "add_to_favorites",
        "delete_for_favorites",
    ]:
        with suppress(TelegramBadRequest):
            await call.message.edit_reply_markup(
                reply_markup=film_kbd(
                    code=callback_data.code,
                    saved=saved,
                    bot_username=bot_username,
                    files=files,
                    current_quality=target_quality,
                    current_language=target_language_res,
                    show_quality_menu=show_quality_menu,
                    show_language_menu=show_language_menu,
                    is_vip=is_vip,
                )
            )
        return

    if callback_data.actions in [ActionType.set_quality, ActionType.set_language]:
        with suppress(TelegramBadRequest):
            await call.message.edit_media(
                InputMediaVideo(
                    media=file_id, caption=caption
                ),
                reply_markup=film_kbd(
                    code=callback_data.code,
                    saved=saved,
                    bot_username=bot_username,
                    files=files,
                    current_quality=target_quality,
                    current_language=target_language_res,
                    show_quality_menu=False,
                    show_language_menu=False,
                    is_vip=is_vip,
                ),
            )
        return


@player_router.callback_query(MiniSeriesPlayerCD.filter())
async def mini_series_player(
    call: CallbackQuery, callback_data: MiniSeriesPlayerCD, session: AsyncSession
):
    favorite_films_actions = FavoriteMoviesActions(session)
    code = callback_data.code

    actions = None
    mini_series_data = await MiniSeriesActions(session).get_mini_series(code)
    if mini_series_data:
        actions = MiniSeriesActions(session)
    if not actions:
        mini_series_data = await MultiFilmMiniSeriesActions(session).get_mini_series(
            code
        )
        if mini_series_data:
            actions = MultiFilmMiniSeriesActions(session)
    if not actions:
        mini_series_data = await AnimeMiniSeriesActions(session).get_mini_series(code)
        if mini_series_data:
            actions = AnimeMiniSeriesActions(session)

    if not actions:
        await call.answer(str(_("❌ Seria topilmadi")), show_alert=True)
        return

    from src.app.database.queries.user import UserActions

    user_actions = UserActions(session)
    db_user = await user_actions.get_user(call.from_user.id)

    from src.app.bot.common.utils import is_active_vip

    is_vip = await is_active_vip(db_user, session)

    bot_info = await call.bot.get_me()
    bot_username = bot_info.username

    saved = await favorite_films_actions.get_favorites(code, call.from_user.id)

    if callback_data.action == "add_to_favorites":
        await favorite_films_actions.add_favorite_movie(
            callback_data.code, call.from_user.id
        )
        saved = True
        await call.answer(str(_("💾 Film sevimlilarga qo‘shildi")))
    elif callback_data.action == "delete_for_favorites":
        await favorite_films_actions.delete_favorite_movie(
            callback_data.code, call.from_user.id
        )
        saved = False
        await call.answer(str(_("❌ Film sevimlilardan o‘chirildi")))

    saved = bool(saved)

    from src.app.bot.common.utils import (
        get_user_language,
        resolve_movie_media,
    )

    user_lang = await get_user_language(call.from_user, session)
    target_language_req = callback_data.language or user_lang

    # Filter data based on selected language
    filtered_mini_series_data = [
        s
        for s in mini_series_data
        if (isinstance(s.files, dict) and target_language_req in s.files)
        or (
            isinstance(s.language, str)
            and target_language_req in (s.language or "").split(",")
        )
    ]
    if not filtered_mini_series_data:
        filtered_mini_series_data = mini_series_data

    serias_count = len(filtered_mini_series_data)

    current_series = next(
        (
            s
            for s in filtered_mini_series_data
            if s.series == callback_data.series_number
        ),
        None,
    )

    if not current_series:
        await call.answer(_("❌ Bu tilda ushbu qism mavjud emas"), show_alert=True)
        return

    if (
        callback_data.action == ActionType.set_quality
        and not is_vip
        and callback_data.quality in ["720p", "1080p"]
    ):
        from src.app.bot.handlers.user.account import vip_tarif_handler

        await call.answer(str(_("💎 VIP obuna talab qilinadi")), show_alert=False)
        await vip_tarif_handler(call.message)
        return

    (
        file_id,
        name,
        caption,
        target_language_res,
        target_quality,
        files,
        _captions,
        thumbnail_id,
    ) = resolve_movie_media(
        current_series, target_language_req, callback_data.quality, is_vip=is_vip
    )

    # If no sub-480p quality available for non-VIP, show VIP prompt
    if not is_vip and target_quality is None:
        from src.app.bot.handlers.user.account import vip_tarif_handler

        await call.answer(str(_("💎 Bu filmni ko'rish uchun VIP obuna talab qilinadi")), show_alert=True)
        await vip_tarif_handler(call.message)
        return

    # files is now the parsed dictionary

    show_quality_menu = callback_data.action == ActionType.open_quality_menu
    show_language_menu = callback_data.action == ActionType.open_language_menu

    if callback_data.action == ActionType.open_series_menu:
        from src.app.bot.keyboards.inline import _build_series_list_menu

        with suppress(TelegramBadRequest):
            await call.message.edit_reply_markup(
                reply_markup=_build_series_list_menu(
                    serias_count=serias_count,
                    current_seria=current_series.series,
                    cd_builder=lambda s: MiniSeriesPlayerCD(
                        code=code,
                        series_number=s,
                        action=(
                            ActionType.next_series
                            if s > current_series.series
                            else ActionType.back_series
                        ),
                        quality=target_quality,
                        language=target_language_res,
                    ).pack(),
                    back_action=True,
                )
            )
        return

    if callback_data.action in [
        ActionType.open_quality_menu,
        ActionType.close_quality_menu,
        ActionType.open_language_menu,
        "add_to_favorites",
        "delete_for_favorites",
    ]:
        with suppress(TelegramBadRequest):
            await call.message.edit_reply_markup(
                reply_markup=mini_series_player_kbd(
                    code=callback_data.code,
                    current_seria=current_series.series,
                    serias_count=serias_count,
                    saved=saved,
                    bot_username=bot_username,
                    files=files,
                    current_quality=target_quality,
                    current_language=target_language_res,
                    show_quality_menu=show_quality_menu,
                    show_language_menu=show_language_menu,
                    is_vip=is_vip,
                )
            )
        return

    with suppress(TelegramBadRequest):
        await call.message.edit_media(
            InputMediaVideo(media=file_id, caption=caption),
            reply_markup=mini_series_player_kbd(
                code=callback_data.code,
                current_seria=current_series.series,
                serias_count=serias_count,
                saved=saved,
                bot_username=bot_username,
                files=files,
                current_quality=target_quality,
                current_language=target_language_res,
                show_quality_menu=False,
                show_language_menu=False,
                is_vip=is_vip,
            ),
        )
