import json
import logging

import redis
import redis.asyncio as aioredis

from utils.config import settings

logger = logging.getLogger(__name__)

# Cache lives in its own Redis DB (separate from the Celery broker), so clearing
# it never touches queued tasks. An empty REDIS_URL turns caching off.
_async_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True) if settings.REDIS_URL else None


async def cache_get(key: str):
    """Return the cached value for `key`, or None on a miss or if Redis is down."""
    if _async_client is None:
        return None
    try:
        value = await _async_client.get(key)
    except redis.RedisError:
        logger.warning("cache read failed for %s", key, exc_info=True)
        return None
    return json.loads(value) if value is not None else None


async def cache_set(key: str, value, ttl: int = settings.CACHE_TTL_SECONDS) -> None:
    """Store a JSON-serializable value under `key` for `ttl` seconds."""
    if _async_client is None:
        return
    try:
        await _async_client.set(key, json.dumps(value, default=str), ex=ttl)
    except redis.RedisError:
        logger.warning("cache write failed for %s", key, exc_info=True)


def clear_cache() -> None:
    """Drop all cached responses. Called by Celery tasks after they change the data."""
    if not settings.REDIS_URL:
        return
    try:
        redis.Redis.from_url(settings.REDIS_URL).flushdb()
    except redis.RedisError:
        logger.warning("cache clear failed", exc_info=True)
