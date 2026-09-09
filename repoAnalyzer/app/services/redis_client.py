from typing import Optional
import redis.asyncio as aioredis
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("redis_client")

_redis_pool: Optional[aioredis.Redis] = None


async def get_redis_client() -> aioredis.Redis:
    """Get or initialize the async Redis client."""
    global _redis_pool
    if _redis_pool is None:
        logger.info("Initializing Redis client connection", url=settings.REDIS_URL)
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


async def close_redis_client() -> None:
    """Close the Redis client connection."""
    global _redis_pool
    if _redis_pool is not None:
        logger.info("Closing Redis connection pool")
        await _redis_pool.aclose()
        _redis_pool = None
