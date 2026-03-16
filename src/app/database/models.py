from datetime import datetime
from sqlalchemy import BigInteger, Text, DateTime, func, JSON
from sqlalchemy.orm import Mapped, mapped_column
from src.app.database.core import Base


class User(Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    language_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_premium: Mapped[bool] = mapped_column(server_default="false", nullable=False)
    vip_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    vip_payment_history: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    vip_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    referral_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    joined_count: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)


class Admin(Base):
    __tablename__ = "admins"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[int] = mapped_column(BigInteger, server_default="1", nullable=False)  # 1: Regular, 2: Super
    is_active: Mapped[bool] = mapped_column(server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)


class Channel(Base):
    __tablename__ = "channels"

    channel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel_name: Mapped[str] = mapped_column(Text, nullable=False)
    channel_username: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_status: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)


class Bot(Base):
    __tablename__ = "bots"

    bot_username: Mapped[str] = mapped_column(Text, primary_key=True)
    bot_name: Mapped[str] = mapped_column(Text, nullable=False)
    bot_status: Mapped[str] = mapped_column(Text, nullable=False)
    bot_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)


class Referral(Base):
    __tablename__ = "referrals"

    referral_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    joined_count: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)


class FeatureFilm(Base):
    __tablename__ = "feature_films"

    code: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[dict] = mapped_column(JSON, nullable=False, index=False)
    video_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    captions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    files: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thumbnails: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    views_count: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)


class Series(Base):
    __tablename__ = "series"

    code: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    season: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    series: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[dict] = mapped_column(JSON, nullable=False)
    video_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    captions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    files: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thumbnails: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    views_count: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)


class MiniSeries(Base):
    __tablename__ = "mini_series"

    code: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    series: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[dict] = mapped_column(JSON, nullable=False)
    video_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    captions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    files: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thumbnails: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    views_count: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)


class Favorite(Base):
    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    movie_code: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)


# --- Multi Film Models ---

class MultiFilmFeature(Base):
    __tablename__ = "multi_film_features"

    code: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[dict] = mapped_column(JSON, nullable=False)
    video_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    captions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    files: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thumbnails: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    views_count: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)


class MultiFilmSeries(Base):
    __tablename__ = "multi_film_series"

    code: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    season: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    series: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[dict] = mapped_column(JSON, nullable=False)
    video_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    captions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    files: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thumbnails: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    views_count: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)


class MultiFilmMiniSeries(Base):
    __tablename__ = "multi_film_mini_series"

    code: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    series: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[dict] = mapped_column(JSON, nullable=False)
    video_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    captions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    files: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thumbnails: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    views_count: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)


# --- Anime Models ---

class AnimeFeature(Base):
    __tablename__ = "anime_features"

    code: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[dict] = mapped_column(JSON, nullable=False)
    video_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    captions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    files: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thumbnails: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    views_count: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)


class AnimeSeries(Base):
    __tablename__ = "anime_series"

    code: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    season: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    series: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[dict] = mapped_column(JSON, nullable=False)
    video_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    captions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    files: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thumbnails: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    views_count: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)


class AnimeMiniSeries(Base):
    __tablename__ = "anime_mini_series"

    code: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    series: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[dict] = mapped_column(JSON, nullable=False)
    video_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    captions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    files: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thumbnails: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    views_count: Mapped[int] = mapped_column(BigInteger, server_default="0", nullable=False)
