import json
from typing import Any, Optional
from redis.asyncio import Redis
import logging

logger = logging.getLogger(__name__)


class CacheService:
    _redis_pool: Optional[Redis] = None
    
    @classmethod
    async def get_redis(cls, redis_url: str) -> Redis:
        import asyncio
        try:
            if cls._redis_pool is not None:
                # Check if the event loop is still running
                await cls._redis_pool.ping()
        except (RuntimeError, Exception):
            # If ping fails or loop is closed, reset the pool
            cls._redis_pool = None

        if cls._redis_pool is None:
            cls._redis_pool = Redis.from_url(
                redis_url,
                max_connections=50,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
            )
            logger.info("Redis connection pool created/recreated")
        return cls._redis_pool
    
    @classmethod
    async def close(cls):
        if cls._redis_pool:
            await cls._redis_pool.close()
            cls._redis_pool = None
            logger.info("Redis connection pool closed")
    
    @classmethod
    async def get_cached(cls, redis_url: str, key: str) -> Optional[Any]:
        try:
            redis = await cls.get_redis(redis_url)
            cached = await redis.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    @classmethod
    async def set_cached(cls, redis_url: str, key: str, value: Any, ttl: int = 300):
        try:
            redis = await cls.get_redis(redis_url)
            await redis.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
    
    @classmethod
    async def delete_cached(cls, redis_url: str, key: str):
        try:
            redis = await cls.get_redis(redis_url)
            await redis.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
    
    @classmethod
    async def delete_pattern(cls, redis_url: str, pattern: str):
        try:
            redis = await cls.get_redis(redis_url)
            keys = []
            async for key in redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await redis.delete(*keys)
                logger.info(f"Deleted {len(keys)} cache keys matching {pattern}")
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
