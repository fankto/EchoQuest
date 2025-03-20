import time
from typing import Dict, Tuple
import asyncio

from loguru import logger

from app.core.config import settings
from app.core.exceptions import RateLimitExceeded


class RateLimiter:
    """
    Rate limiter for API endpoints.
    Uses a simple in-memory token bucket algorithm.
    In a production environment, this should be replaced with a Redis-based implementation.
    """

    def __init__(self):
        self.tokens: Dict[str, Tuple[int, float]] = {}  # {token: (remaining_requests, last_reset_time)}
        self.lock = asyncio.Lock()

    async def check_rate_limit(self, token: str) -> None:
        """
        Check if a request should be rate limited.

        Args:
            token: JWT token or other identifier

        Raises:
            RateLimitExceeded: If rate limit exceeded
        """
        if not settings.RATE_LIMIT_ENABLED:
            return

        async with self.lock:
            now = time.time()

            # Get current bucket or create new one
            remaining, last_reset = self.tokens.get(token, (settings.RATE_LIMIT_DEFAULT_LIMIT, now))

            # Check if bucket should be refilled
            time_passed = now - last_reset
            if time_passed >= settings.RATE_LIMIT_DEFAULT_PERIOD:
                # Reset bucket
                self.tokens[token] = (settings.RATE_LIMIT_DEFAULT_LIMIT, now)
                return

            # Check if requests remaining
            if remaining <= 0:
                # Calculate retry after header value
                retry_after = int(settings.RATE_LIMIT_DEFAULT_PERIOD - time_passed) + 1
                logger.warning(f"Rate limit exceeded for token {token[:10]}..., retry after {retry_after}s")
                raise RateLimitExceeded(
                    detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    retry_after=retry_after
                )

            # Decrement remaining tokens
            self.tokens[token] = (remaining - 1, last_reset)

    async def reset_limit(self, token: str) -> None:
        """
        Reset rate limit for a token

        Args:
            token: Token to reset
        """
        async with self.lock:
            now = time.time()
            self.tokens[token] = (settings.RATE_LIMIT_DEFAULT_LIMIT, now)


# Create singleton instance
rate_limiter = RateLimiter()