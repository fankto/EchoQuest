import redis.asyncio as redis
from loguru import logger

from app.core.config import settings

# Redis client singleton
_redis_client = None


async def get_redis_client():
    """
    Get or create Redis client

    Returns:
        Redis client or None if Redis is not configured
    """
    global _redis_client

    if not settings.REDIS_ENABLED:
        return None

    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=False
            )
            # Test connection
            await _redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            _redis_client = None

    return _redis_client


async def close_redis_connection():
    """Close Redis connection if open"""
    global _redis_client

    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")