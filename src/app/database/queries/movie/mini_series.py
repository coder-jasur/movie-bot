from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
import logging

from src.app.database.models import MiniSeries

logger = logging.getLogger(__name__)


class MiniSeriesActions:
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

        ms = MiniSeries(
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
            stmt = update(MiniSeries).where(MiniSeries.code == mini_series_code).values(genres=genres)
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
        stmt = select(MiniSeries).where(
            MiniSeries.code == mini_series_code,
            MiniSeries.series == series_num
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
            try:
                import json
                parsed = json.loads(episode.captions)
                if isinstance(parsed, dict):
                    current_captions = parsed
                else:
                    current_captions = {"uz": episode.captions}
            except:
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
        stmt = select(MiniSeries).where(
            MiniSeries.code == mini_series_code,
            MiniSeries.series == series_num
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
            try:
                import json
                parsed = json.loads(episode.captions)
                if isinstance(parsed, dict):
                    current_captions = parsed
                else:
                    current_captions = {"uz": episode.captions}
            except:
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
        stmt = select(MiniSeries).where(
            MiniSeries.code == mini_series_code,
            MiniSeries.series == series_num
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

    async def get_mini_series(self, mini_series_code: int) -> list[MiniSeries]:
        try:
            stmt = select(MiniSeries).where(MiniSeries.code == mini_series_code).order_by(MiniSeries.series)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting mini series {mini_series_code}: {e}")
            return []

    async def delete_mini_series(self, mini_series_code: int):
        stmt = delete(MiniSeries).where(MiniSeries.code == mini_series_code)
        await self.session.execute(stmt)
        await self.session.commit()

    async def delete_mini_series_for_series(self, mini_series_code: int, series: int):
        stmt = delete(MiniSeries).where(
            MiniSeries.code == mini_series_code,
            MiniSeries.series == series
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_all_mini_series(self) -> list[MiniSeries]:
        try:
            stmt = select(MiniSeries)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting all mini series: {e}")
            return []

    async def update_mini_series(self, mini_series_code: int, **values):
        """Update metadata (Name/Caption) for ALL episodes of a mini-series code."""
        stmt = update(MiniSeries).where(MiniSeries.code == mini_series_code).values(**values)
        await self.session.execute(stmt)
        await self.session.commit()

    async def update_episode_file(self, mini_series_code: int, series_num: int, language: str, quality: str, file_id: str):
        """Update file_id for a specific episode track."""
        episode = await self.session.execute(
            select(MiniSeries).where(MiniSeries.code == mini_series_code, MiniSeries.series == series_num)
        )
        episode = episode.scalar_one_or_none()
        if episode:
            if not isinstance(episode.files, dict):
                episode.files = {}
            if language not in episode.files:
                episode.files[language] = {}
            episode.files[language][quality] = file_id
            flag_modified(episode, "files")
            await self.session.commit()

    async def update_movie_code(self, old_code: int, new_code: int) -> None:
        """
        Update the mini-series code for all episodes.
        """
        # Check if new code exists
        existing = await self.get_mini_series(new_code)
        if existing:
            raise ValueError(f"Code {new_code} already exists")

        stmt = (
            update(MiniSeries)
            .where(MiniSeries.code == old_code)
            .values(code=new_code)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def update_episode_details(self, mini_series_code: int, old_series: int, **values):
        """
        Update specific episode details (series number).
        """
        stmt = update(MiniSeries).where(
            MiniSeries.code == mini_series_code,
            MiniSeries.series == old_series
        ).values(**values)
        await self.session.execute(stmt)
        await self.session.commit()

    async def update_episode_metadata(self, mini_series_code: int, series_num: int, **values):
        """Update name/caption for a specific episode."""
        stmt = update(MiniSeries).where(
            MiniSeries.code == mini_series_code,
            MiniSeries.series == series_num
        ).values(**values)
        await self.session.execute(stmt)
        await self.session.commit()

    async def update_genres(self, mini_series_code: int, genres: str) -> None:
        """Update genres for all episodes of a mini-series code."""
        stmt = update(MiniSeries).where(MiniSeries.code == mini_series_code).values(genres=genres)
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_genres_by_code(self, mini_series_code: int) -> str | None:
        """Get genres for a mini-series code (from first available episode)."""
        stmt = select(MiniSeries.genres).where(MiniSeries.code == mini_series_code).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def move_to_feature_film(self, mini_series_code: int, series_num: int, new_code: int):
        """Moves a mini-series episode to FeatureFilm table with a new code."""
        # Get the episode
        stmt = select(MiniSeries).where(
            MiniSeries.code == mini_series_code,
            MiniSeries.series == series_num
        )
        result = await self.session.execute(stmt)
        episode = result.scalar_one_or_none()
        if not episode:
            raise ValueError("Episode not found")

        # Create new FeatureFilm
        from src.app.database.models import FeatureFilm
        new_film = FeatureFilm(
            code=new_code,
            name=episode.name,
            captions=episode.captions
        )
        self.session.add(new_film)
        
        # Delete from MiniSeries
        await self.session.delete(episode)
        await self.session.commit()

    async def get_random_mini_series_first_episode(self) -> MiniSeries | None:
        """
        Get random mini-series, but only its first episode (series = 1).
        """
        try:
            stmt = (
                select(MiniSeries)
                .where(MiniSeries.series == 1)
                .order_by(func.random())
                .limit(1)
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting random mini series: {e}")
            return None
    async def get_top_viewed_movies(self, limit: int = 20):
        stmt = (
            select(MiniSeries.code, func.sum(MiniSeries.views_count).label("count"))
            .group_by(MiniSeries.code)
            .order_by(func.sum(MiniSeries.views_count).desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.all()

    async def increment_views(self, mini_series_code: int, series_num: int = 1):
        stmt = (
            update(MiniSeries)
            .where(MiniSeries.code == mini_series_code, MiniSeries.series == series_num)
            .values(views_count=MiniSeries.views_count + 1)
        )
        await self.session.execute(stmt)
        await self.session.commit()
