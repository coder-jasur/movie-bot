from typing import Sequence

from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
import logging

from src.app.database.models import FeatureFilm

logger = logging.getLogger(__name__)


class FeatureFilmsActions:
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
        # Initial track setup
        # Initial track setup
        lang_key = language or "uz"  # default if not provided
        
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

        film = FeatureFilm(
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

        # Log state before update
        logger.info(f"Adding Language Track for Film {film_code} - Language: {language}")
        logger.info(f"Current Files: {film.files}")
        logger.info(f"Current Captions: {film.captions}")

        # Ensure we work with dictionaries and don't lose legacy string data
        if isinstance(film.files, dict):
            current_files = dict(film.files)
        else:
            current_files = {}

        if isinstance(film.captions, dict):
            current_captions = dict(film.captions)
        elif isinstance(film.captions, str) and film.captions.strip():
            # Try to parse as JSON in case it's a serialized dict
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

        # Ensure caption is a string, not a dict (prevents nesting)
        if isinstance(caption, dict):
            caption = caption.get(language, str(caption))
        current_captions[language] = caption
        
        # Update language list
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

        # Explicitly mark as modified for SQLAlchemy JSON detection
        flag_modified(film, "files")
        flag_modified(film, "captions")
        
        logger.info(f"Updated Files: {film.files}")
        logger.info(f"Updated Captions: {film.captions}")
        
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

    async def get_feature_film(self, film_code: int) -> FeatureFilm | None:
        try:
            stmt = select(FeatureFilm).where(FeatureFilm.code == film_code)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting feature film {film_code}: {e}")
            return None

    async def get_top_viewed_movies(self, limit: int = 20):
        stmt = select(FeatureFilm.code, FeatureFilm.views_count).order_by(FeatureFilm.views_count.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.all()

    async def increment_views(self, film_code: int):
        stmt = update(FeatureFilm).where(FeatureFilm.code == film_code).values(views_count=FeatureFilm.views_count + 1)
        await self.session.execute(stmt)
        await self.session.commit()

    async def delete_feature_film(self, film_code: int):
        stmt = delete(FeatureFilm).where(FeatureFilm.code == film_code)
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_all_feature_films(self) -> Sequence[FeatureFilm]:

        stmt = select(FeatureFilm)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_feature_film(self, film_code: int, **values):
        stmt = update(FeatureFilm).where(FeatureFilm.code == film_code).values(**values)
        await self.session.execute(stmt)
        await self.session.commit()

    async def update_genres(self, film_code: int, genres: str) -> None:
        """Update genres for a feature film."""
        stmt = update(FeatureFilm).where(FeatureFilm.code == film_code).values(genres=genres)
        await self.session.execute(stmt)
        await self.session.commit()

    async def update_movie_code(self, old_code: int, new_code: int) -> None:
        """
        Update the movie code.
        """
        # Check if new code exists
        existing = await self.get_feature_film(new_code)
        if existing:
            raise ValueError(f"Code {new_code} already exists")

        stmt = (
            update(FeatureFilm)
            .where(FeatureFilm.code == old_code)
            .values(code=new_code)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_random_feature_film(self) -> FeatureFilm | None:
        """
        Get one random feature film from database.
        """
        try:
            stmt = select(FeatureFilm).order_by(func.random()).limit(1)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting random feature film: {e}")
            return None