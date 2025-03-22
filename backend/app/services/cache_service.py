import json
from typing import Any, Dict, List, Optional, TypeVar, Type, Generic, Union, Callable
import pickle
import hashlib
import inspect
from functools import wraps

import redis.asyncio as redis
from pydantic import BaseModel
from loguru import logger

from app.core.config import settings
from app.core.exceptions import ExternalServiceError

T = TypeVar('T')
ModelT = TypeVar('ModelT', bound=BaseModel)


class CacheService:
    """
    Service for interacting with Redis cache

    Provides methods for storing and retrieving data from Redis with
    proper serialization, error handling, and TTL management.
    """

    def __init__(self):
        self._redis_client = None
        self.ttl = 3600  # Default TTL of 1 hour
        self.enabled = settings.REDIS_ENABLED
        logger.info(f"Cache service initialized with enabled={self.enabled}")

    async def get_client(self) -> Optional[redis.Redis]:
        """
        Get or create Redis client

        Returns:
            Redis client or None if Redis is not configured

        Raises:
            ExternalServiceError: If there's an error connecting to Redis
        """
        if not self.enabled:
            return None

        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=False
                )

                # Test connection
                await self._redis_client.ping()
                logger.info("Redis connection established")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self._redis_client = None
                raise ExternalServiceError("Redis", f"Connection error: {str(e)}")

        return self._redis_client

    async def close(self) -> None:
        """Close Redis connection if open"""
        if self._redis_client is not None:
            await self._redis_client.close()
            self._redis_client = None
            logger.info("Redis connection closed")

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate a cache key based on function arguments

        Args:
            prefix: Key prefix
            *args: Function positional arguments
            **kwargs: Function keyword arguments

        Returns:
            Cache key
        """
        # Create a string representation of args and kwargs
        key_parts = [prefix]

        # Add args
        for arg in args:
            if isinstance(arg, (str, int, float, bool, type(None))):
                key_parts.append(str(arg))
            elif hasattr(arg, '__dict__'):  # Custom objects
                key_parts.append(hashlib.md5(str(arg.__dict__).encode()).hexdigest())
            else:
                key_parts.append(hashlib.md5(str(arg).encode()).hexdigest())

        # Add kwargs (sorted for deterministic keys)
        for k, v in sorted(kwargs.items()):
            if isinstance(v, (str, int, float, bool, type(None))):
                key_parts.append(f"{k}={v}")
            elif hasattr(v, '__dict__'):  # Custom objects
                key_parts.append(f"{k}={hashlib.md5(str(v.__dict__).encode()).hexdigest()}")
            else:
                key_parts.append(f"{k}={hashlib.md5(str(v).encode()).hexdigest()}")

        # Join parts with ':'
        return ":".join(key_parts)

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from cache

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        if not self.enabled:
            return default

        try:
            client = await self.get_client()
            if not client:
                return default

            data = await client.get(key)
            if data is None:
                return default

            return pickle.loads(data)
        except Exception as e:
            logger.error(f"Error getting from cache ({key}): {e}")
            return default

    async def set(
            self,
            key: str,
            value: Any,
            ttl: Optional[int] = None
    ) -> bool:
        """
        Set a value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None for default)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            client = await self.get_client()
            if not client:
                return False

            # Use specified TTL or default
            expiration = ttl if ttl is not None else self.ttl

            # Serialize value
            serialized = pickle.dumps(value)

            # Set in Redis
            await client.set(key, serialized, ex=expiration)
            return True
        except Exception as e:
            logger.error(f"Error setting cache ({key}): {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete a value from cache

        Args:
            key: Cache key

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            client = await self.get_client()
            if not client:
                return False

            await client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting from cache ({key}): {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching a pattern

        Args:
            pattern: Key pattern to match

        Returns:
            Number of keys deleted
        """
        if not self.enabled:
            return 0

        try:
            client = await self.get_client()
            if not client:
                return 0

            # Get matching keys
            keys = []
            async for key in client.scan_iter(pattern):
                keys.append(key)

            # Delete keys if any found
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Error clearing cache pattern ({pattern}): {e}")
            return 0

    def cached(
            self,
            ttl: Optional[int] = None,
            prefix: Optional[str] = None
    ) -> Callable:
        """
        Decorator for caching function results

        Args:
            ttl: Optional TTL override
            prefix: Optional key prefix override

        Returns:
            Decorated function
        """

        def decorator(func):
            # Get function information for key generation
            func_module = func.__module__
            func_name = func.__name__
            key_prefix = prefix or f"{func_module}.{func_name}"

            @wraps(func)
            async def wrapper(*args, **kwargs):
                if not self.enabled:
                    return await func(*args, **kwargs)

                # Generate cache key
                cache_key = self._generate_key(key_prefix, *args, **kwargs)

                # Try to get from cache
                cached_value = await self.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache hit: {cache_key}")
                    return cached_value

                # Call function if not in cache
                logger.debug(f"Cache miss: {cache_key}")
                result = await func(*args, **kwargs)

                # Cache result
                await self.set(cache_key, result, ttl)

                return result

            return wrapper

        return decorator

    async def get_model(
            self,
            key: str,
            model_class: Type[ModelT]
    ) -> Optional[ModelT]:
        """
        Get a Pydantic model from cache

        Args:
            key: Cache key
            model_class: Pydantic model class

        Returns:
            Pydantic model instance or None if not found
        """
        data = await self.get(key)
        if data is None:
            return None

        return model_class.model_validate(data)

    async def set_model(
            self,
            key: str,
            model: ModelT,
            ttl: Optional[int] = None
    ) -> bool:
        """
        Set a Pydantic model in cache

        Args:
            key: Cache key
            model: Pydantic model instance
            ttl: Time to live in seconds (None for default)

        Returns:
            True if successful, False otherwise
        """
        # Convert model to dict
        data = model.model_dump()
        return await self.set(key, data, ttl)


# Create singleton instance
cache_service = CacheService()