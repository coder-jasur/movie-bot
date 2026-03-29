from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
import logging

from src.app.database.models import MultiFilmFeature, MultiFilmSeries, MultiFilmMiniSeries

logger = logging.getLogger(__name__)


class MultiFilmFeatureActions:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_feature_film(
            self,
            film_code: int,
            film_name: str,
            caption: str,
            genres: str = None,
            language: str = None,
            files: dict = None,
            thumbnail_file_id: str = None,
    ):
        lang_key = language or "uz"
        
        # Determine structured names/captions - prioritize existing dicts
        if isinstance(film_name, dict):
            structured_names = film_name
        else:
            structured_names = {lang_key: film_name}

        if isinstance(caption, dict):
            structured_captions = caption
        else:
            structured_captions = {lang_key: caption} if caption else {}

        structured_files = {lang_key: files or {}}
        structured_thumbnails = {lang_key: thumbnail_file_id} if thumbnail_file_id else {}

        film = MultiFilmFeature(
            code=film_code,
            name=structured_names,
            captions=structured_captions,
            genres=genres,
            language=language or lang_key,
            files=structured_files,
            thumbnails=structured_thumbnails
        )
        self.session.add(film)
        await self.session.commit()

    async def add_language_track(
            self,
            film_code: int,
            language: str,
            caption: str,
            files: dict = None,
            name: str = None,
            thumbnail_file_id: str = None,
    ):
        film = await self.get_feature_film(film_code)
        if not film:
            raise ValueError(f"Film with code {film_code} not found")
        
        # Handle localized names
        if isinstance(film.name, dict):
            current_names = dict(film.name)
        else:
            current_names = {"uz": str(film.name)} if film.name else {}

        if name:
            current_names[language] = name
            film.name = current_names
            flag_modified(film, "name")

        if isinstance(film.files, dict):
            current_files = dict(film.files)
        else:
            current_files = {}

        if isinstance(film.captions, dict):
            current_captions = dict(film.captions)
        elif isinstance(film.captions, str) and film.captions.strip():
            try:
                import json
                parsed = json.loads(film.captions)
                if isinstance(parsed, dict):
                    current_captions = parsed
                else:
                    current_captions = {"uz": film.captions}
            except:
                current_captions = {"uz": film.captions}
        else:
            current_captions = {}
            
        if language not in current_files or not isinstance(current_files[language], dict):
            current_files[language] = {}

        if files:
            current_files[language].update(files)

        current_captions[language] = caption
        
        current_langs = [l for l in (film.language or "").split(",") if l]
        if language not in current_langs:
            current_langs.append(language)
        
        film.language = ",".join(current_langs)
        film.files = current_files
        film.captions = current_captions

        if thumbnail_file_id:
            if not isinstance(film.thumbnails, dict):
                film.thumbnails = {}
            film.thumbnails[language] = thumbnail_file_id
            flag_modified(film, "thumbnails")

        flag_modified(film, "files")
        flag_modified(film, "captions")
        
        await self.session.commit()

    async def update_language_track(
            self,
            film_code: int,
            language: str,
            caption: str = None,
            files: dict = None,
            name: str = None,
            thumbnail_file_id: str = None,
            clear_files: bool = False
    ):
        film = await self.get_feature_film(film_code)
        if not film:
            raise ValueError(f"Film {film_code} not found")

        if isinstance(film.files, dict):
            current_files = dict(film.files)
        else:
            current_files = {}

        if isinstance(film.captions, dict):
            current_captions = dict(film.captions)
        elif isinstance(film.captions, str) and film.captions.strip():
            try:
                import json
                parsed = json.loads(film.captions)
                if isinstance(parsed, dict):
                    current_captions = parsed
                else:
                    current_captions = {"uz": film.captions}
            except:
                current_captions = {"uz": film.captions}
        else:
            current_captions = {}

        if isinstance(film.name, dict):
            current_names = dict(film.name)
        else:
            current_names = {"uz": str(film.name)} if film.name else {}

        if files:
            if language not in current_files or not isinstance(current_files[language], dict) or clear_files:
                current_files[language] = {}
            
            current_files[language].update(files)
                
            film.files = current_files
            flag_modified(film, "files")
        
        if caption is not None:
            current_captions[language] = caption
            film.captions = current_captions
            flag_modified(film, "captions")

        if name is not None:
            current_names[language] = name
            film.name = current_names
            flag_modified(film, "name")

        # Ensure language is added to the language list
        current_langs = [l for l in (film.language or "").split(",") if l]
        if language not in current_langs:
            current_langs.append(language)
            film.language = ",".join(current_langs)

        if thumbnail_file_id is not None:
            if not isinstance(film.thumbnails, dict):
                film.thumbnails = {}
            film.thumbnails[language] = thumbnail_file_id
            flag_modified(film, "thumbnails")

        await self.session.commit()

    async def delete_language_track(self, film_code: int, language: str):
        film = await self.get_feature_film(film_code)
        if not film: return

        current_files = dict(film.files) if isinstance(film.files, dict) else {}
        current_captions = dict(film.captions) if isinstance(film.captions, dict) else {}
        current_langs = (film.language or "").split(",")

        if language in current_files:
            del current_files[language]
        if language in current_captions:
            del current_captions[language]
        if language in current_langs:
            current_langs.remove(language)

        film.files = current_files
        film.captions = current_captions
        film.language = ",".join(filter(None, current_langs))
        flag_modified(film, "files")
        flag_modified(film, "captions")

        await self.session.commit()

    async def get_feature_film(self, film_code: int) -> MultiFilmFeature | None:
        try:
            stmt = select(MultiFilmFeature).where(MultiFilmFeature.code == film_code)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting multi film feature {film_code}: {e}")
            return None

    async def get_random_feature_film(self) -> MultiFilmFeature | None:
        try:
            stmt = select(MultiFilmFeature).order_by(func.random()).limit(1)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting random multi film feature: {e}")
            return None

    async def increment_views(self, film_code: int):
        stmt = update(MultiFilmFeature).where(MultiFilmFeature.code == film_code).values(views_count=MultiFilmFeature.views_count + 1)
        await self.session.execute(stmt)
        await self.session.commit()


class MultiFilmSeriesActions:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_series(
            self,
            series_code: int,
            series_name: str,
            series_num: int,
            season: int,
            caption: str,
            genres: str = None,
            language: str = None,
            files: dict = None,
            thumbnail_file_id: str = None,
    ):
        lang_key = language or "uz"
        
        # Determine structured names/captions - prioritize existing dicts
        if isinstance(series_name, dict):
            structured_names = series_name
        else:
            structured_names = {lang_key: series_name}

        if isinstance(caption, dict):
            structured_captions = caption
        else:
            structured_captions = {lang_key: caption} if caption else {}

        structured_files = {lang_key: files or {}}
        structured_thumbnails = {lang_key: thumbnail_file_id} if thumbnail_file_id else {}

        s = MultiFilmSeries(
            code=series_code,
            name=structured_names,
            season=season,
            series=series_num,
            captions=structured_captions,
            genres=genres,
            language=language or lang_key,
            files=structured_files,
            thumbnails=structured_thumbnails
        )
        # Update genres, format for all other episodes of the same series
        if genres:
            stmt = update(MultiFilmSeries).where(MultiFilmSeries.code == series_code).values(genres=genres)
            await self.session.execute(stmt)
            
        self.session.add(s)
        await self.session.commit()

    async def add_language_track(
            self,
            series_code: int,
            season: int,
            series_num: int,
            language: str,
            caption: str,
            files: dict = None,
            name: str = None,
            thumbnail_file_id: str = None,
    ):
        stmt = select(MultiFilmSeries).where(
            MultiFilmSeries.code == series_code,
            MultiFilmSeries.season == season,
            MultiFilmSeries.series == series_num
        )
        result = await self.session.execute(stmt)
        episode = result.scalar_one_or_none()
        
        if not episode:
            raise ValueError(f"Episode {series_num} S{season} of series {series_code} not found")

        if isinstance(episode.files, dict):
            current_files = dict(episode.files)
        else:
            current_files = {}

        if isinstance(episode.captions, dict):
            current_captions = dict(episode.captions)
        elif isinstance(episode.captions, str) and episode.captions.strip():
            current_captions = {"uz": episode.captions}
        else:
            current_captions = {}

        if isinstance(episode.name, dict):
            current_names = dict(episode.name)
        else:
            current_names = {"uz": str(episode.name)} if episode.name else {}

        if name:
            current_names[language] = name
            episode.name = current_names
            flag_modified(episode, "name")
        
        if language not in current_files or not isinstance(current_files[language], dict):
            current_files[language] = {}

        if files:
            current_files[language].update(files)

        current_captions[language] = caption
        
        current_langs = [l for l in (episode.language or "").split(",") if l]
        if language not in current_langs:
            current_langs.append(language)
        
        episode.language = ",".join(current_langs)
        episode.files = current_files
        episode.captions = current_captions

        if thumbnail_file_id:
            if not isinstance(episode.thumbnails, dict):
                episode.thumbnails = {}
            episode.thumbnails[language] = thumbnail_file_id
            flag_modified(episode, "thumbnails")

        flag_modified(episode, "files")
        flag_modified(episode, "captions")
        
        await self.session.commit()

    async def update_language_track(
            self,
            series_code: int,
            season: int,
            series_num: int,
            language: str,
            caption: str = None,
            files: dict = None,
            name: str = None,
            thumbnail_file_id: str = None,
            clear_files: bool = False
    ):
        stmt = select(MultiFilmSeries).where(
            MultiFilmSeries.code == series_code,
            MultiFilmSeries.season == season,
            MultiFilmSeries.series == series_num
        )
        result = await self.session.execute(stmt)
        episode = result.scalar_one_or_none()
        
        if not episode:
            raise ValueError(f"Episode {series_num} S{season} not found")

        if isinstance(episode.files, dict):
            current_files = dict(episode.files)
        else:
            current_files = {}

        if isinstance(episode.captions, dict):
            current_captions = dict(episode.captions)
        elif isinstance(episode.captions, str) and episode.captions.strip():
            current_captions = {"uz": episode.captions}
        else:
            current_captions = {}

        if isinstance(episode.name, dict):
            current_names = dict(episode.name)
        else:
            current_names = {"uz": str(episode.name)} if episode.name else {}

        if files:
            if language not in current_files or not isinstance(current_files[language], dict) or clear_files:
                current_files[language] = {}
            
            current_files[language].update(files)
                
            episode.files = current_files
            flag_modified(episode, "files")
        
        if caption is not None:
            current_captions[language] = caption
            episode.captions = current_captions
            flag_modified(episode, "captions")

        if name is not None:
            current_names[language] = name
            episode.name = current_names
            flag_modified(episode, "name")

        # Ensure language is added to the language list
        current_langs = [l for l in (episode.language or "").split(",") if l]
        if language not in current_langs:
            current_langs.append(language)
            episode.language = ",".join(current_langs)

        if thumbnail_file_id is not None:
            if not isinstance(episode.thumbnails, dict):
                episode.thumbnails = {}
            episode.thumbnails[language] = thumbnail_file_id
            flag_modified(episode, "thumbnails")

        await self.session.commit()

    async def delete_language_track(self, series_code: int, season: int, series_num: int, language: str):
        stmt = select(MultiFilmSeries).where(
            MultiFilmSeries.code == series_code,
            MultiFilmSeries.season == season,
            MultiFilmSeries.series == series_num
        )
        result = await self.session.execute(stmt)
        episode = result.scalar_one_or_none()
        
        if not episode: return

        current_files = dict(episode.files) if isinstance(episode.files, dict) else {}
        current_captions = dict(episode.captions) if isinstance(episode.captions, dict) else {}
        current_langs = (episode.language or "").split(",")

        if language in current_files:
            del current_files[language]
        if language in current_captions:
            del current_captions[language]
        if language in current_langs:
            current_langs.remove(language)

        episode.files = current_files
        episode.captions = current_captions
        episode.language = ",".join(filter(None, current_langs))
        flag_modified(episode, "files")
        flag_modified(episode, "captions")

        await self.session.commit()

    async def get_series(self, series_code: int) -> list[MultiFilmSeries]:
        try:
            stmt = select(MultiFilmSeries).where(MultiFilmSeries.code == series_code).order_by(MultiFilmSeries.season, MultiFilmSeries.series)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting multi film series {series_code}: {e}")
            return []

    async def get_random_series_first_episode(self) -> MultiFilmSeries | None:
        try:
            stmt = (
                select(MultiFilmSeries)
                .where(MultiFilmSeries.season == 1, MultiFilmSeries.series == 1)
                .order_by(func.random())
                .limit(1)
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting random multi film series: {e}")
            return None

    async def increment_views(self, series_code: int, season: int = 1, series_num: int = 1):
        stmt = (
            update(MultiFilmSeries)
            .where(MultiFilmSeries.code == series_code, MultiFilmSeries.season == season, MultiFilmSeries.series == series_num)
            .values(views_count=MultiFilmSeries.views_count + 1)
        )
        await self.session.execute(stmt)
        await self.session.commit()


class MultiFilmMiniSeriesActions:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_mini_series(
            self,
            mini_series_code: int,
            mini_series_name: str,
            series: int,
            caption: str,
            genres: str = None,
            language: str = None,
            files: dict = None,
            thumbnail_file_id: str = None,
    ):
        lang_key = language or "uz"
        
        # Determine structured names/captions - prioritize existing dicts
        if isinstance(mini_series_name, dict):
            structured_names = mini_series_name
        else:
            structured_names = {lang_key: mini_series_name}

        if isinstance(caption, dict):
            structured_captions = caption
        else:
            structured_captions = {lang_key: caption} if caption else {}

        structured_files = {lang_key: files or {}}
        structured_thumbnails = {lang_key: thumbnail_file_id} if thumbnail_file_id else {}

        ms = MultiFilmMiniSeries(
            code=mini_series_code,
            name=structured_names,
            series=series,
            captions=structured_captions,
            genres=genres,
            language=language or lang_key,
            files=structured_files,
            thumbnails=structured_thumbnails
        )
        
        if genres:
            stmt = update(MultiFilmMiniSeries).where(MultiFilmMiniSeries.code == mini_series_code).values(genres=genres)
            await self.session.execute(stmt)

        self.session.add(ms)
        await self.session.commit()

    async def add_language_track(
            self,
            mini_series_code: int,
            series_num: int,
            language: str,
            caption: str,
            files: dict = None,
            name: str = None,
            thumbnail_file_id: str = None,
    ):
        stmt = select(MultiFilmMiniSeries).where(
            MultiFilmMiniSeries.code == mini_series_code,
            MultiFilmMiniSeries.series == series_num
        )
        result = await self.session.execute(stmt)
        episode = result.scalar_one_or_none()
        
        if not episode:
            raise ValueError(f"Episode {series_num} of mini-series {mini_series_code} not found")

        if isinstance(episode.files, dict):
            current_files = dict(episode.files)
        else:
            current_files = {}

        if isinstance(episode.captions, dict):
            current_captions = dict(episode.captions)
        elif isinstance(episode.captions, str) and episode.captions.strip():
            current_captions = {"uz": episode.captions}
        else:
            current_captions = {}

        if isinstance(episode.name, dict):
            current_names = dict(episode.name)
        else:
            current_names = {"uz": str(episode.name)} if episode.name else {}

        if name:
            current_names[language] = name
            episode.name = current_names
            flag_modified(episode, "name")
        if language not in current_files or not isinstance(current_files[language], dict):
            current_files[language] = {}

        if files:
            current_files[language].update(files)

        current_captions[language] = caption
        
        current_langs = [l for l in (episode.language or "").split(",") if l]
        if language not in current_langs:
            current_langs.append(language)
        
        episode.language = ",".join(current_langs)
        episode.files = current_files
        episode.captions = current_captions

        if thumbnail_file_id:
            if not isinstance(episode.thumbnails, dict):
                episode.thumbnails = {}
            episode.thumbnails[language] = thumbnail_file_id
            flag_modified(episode, "thumbnails")

        flag_modified(episode, "files")
        flag_modified(episode, "captions")
        
        await self.session.commit()

    async def update_language_track(
            self,
            mini_series_code: int,
            series_num: int,
            language: str,
            caption: str = None,
            files: dict = None,
            name: str = None,
            thumbnail_file_id: str = None,
            clear_files: bool = False
    ):
        stmt = select(MultiFilmMiniSeries).where(
            MultiFilmMiniSeries.code == mini_series_code,
            MultiFilmMiniSeries.series == series_num
        )
        result = await self.session.execute(stmt)
        episode = result.scalar_one_or_none()
        
        if not episode:
            raise ValueError(f"Episode {series_num} not found")

        if isinstance(episode.files, dict):
            current_files = dict(episode.files)
        else:
            current_files = {}

        if isinstance(episode.captions, dict):
            current_captions = dict(episode.captions)
        elif isinstance(episode.captions, str) and episode.captions.strip():
            current_captions = {"uz": episode.captions}
        else:
            current_captions = {}

        if isinstance(episode.name, dict):
            current_names = dict(episode.name)
        else:
            current_names = {"uz": str(episode.name)} if episode.name else {}

        if files:
            if language not in current_files or not isinstance(current_files[language], dict) or clear_files:
                current_files[language] = {}
            
            current_files[language].update(files)
                
            episode.files = current_files
            flag_modified(episode, "files")
        
        if caption is not None:
            current_captions[language] = caption
            episode.captions = current_captions
            flag_modified(episode, "captions")

        if name is not None:
            current_names[language] = name
            episode.name = current_names
            flag_modified(episode, "name")

        # Ensure language is added to the language list
        current_langs = [l for l in (episode.language or "").split(",") if l]
        if language not in current_langs:
            current_langs.append(language)
            episode.language = ",".join(current_langs)

        if thumbnail_file_id is not None:
            if not isinstance(episode.thumbnails, dict):
                episode.thumbnails = {}
            episode.thumbnails[language] = thumbnail_file_id
            flag_modified(episode, "thumbnails")

        await self.session.commit()

    async def delete_language_track(self, mini_series_code: int, series_num: int, language: str):
        stmt = select(MultiFilmMiniSeries).where(
            MultiFilmMiniSeries.code == mini_series_code,
            MultiFilmMiniSeries.series == series_num
        )
        result = await self.session.execute(stmt)
        episode = result.scalar_one_or_none()
        
        if not episode: return

        current_files = dict(episode.files) if episode.files else {}
        current_captions = dict(episode.captions) if episode.captions else {}
        current_langs = (episode.language or "").split(",")

        if language in current_files:
            del current_files[language]
        if language in current_captions:
            del current_captions[language]
        if language in current_langs:
            current_langs.remove(language)

        episode.files = current_files
        episode.captions = current_captions
        episode.language = ",".join(filter(None, current_langs))
        flag_modified(episode, "files")
        flag_modified(episode, "captions")

        await self.session.commit()

    async def get_mini_series(self, mini_series_code: int) -> list[MultiFilmMiniSeries]:
        try:
            stmt = select(MultiFilmMiniSeries).where(MultiFilmMiniSeries.code == mini_series_code).order_by(MultiFilmMiniSeries.series)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting multi film mini series {mini_series_code}: {e}")
            return []

    async def get_random_mini_series_first_episode(self) -> MultiFilmMiniSeries | None:
        try:
            stmt = (
                select(MultiFilmMiniSeries)
                .where(MultiFilmMiniSeries.series == 1)
                .order_by(func.random())
                .limit(1)
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting random multi film mini series: {e}")
            return None

    async def increment_views(self, mini_series_code: int, series_num: int = 1):
        stmt = (
            update(MultiFilmMiniSeries)
            .where(MultiFilmMiniSeries.code == mini_series_code, MultiFilmMiniSeries.series == series_num)
            .values(views_count=MultiFilmMiniSeries.views_count + 1)
        )
        await self.session.execute(stmt)
        await self.session.commit()
