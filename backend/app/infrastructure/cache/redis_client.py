"""Redis cache and distributed state management service abstraction."""

import time
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio.client import Redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.infrastructure.cache")


class RedisService:
    """Async Redis client wrapper providing caching, session, and rate-limiting foundations."""

    def __init__(self, url: str = settings.REDIS_URL):
        self._url = url
        self._client: Redis | None = None

    async def get_client(self) -> Redis:
        """Lazily initializes and returns the async Redis client instance."""
        if self._client is None:
            self._client = aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
            )
        return self._client

    async def check_health(self) -> dict[str, Any]:
        """Pings Redis to verify connectivity and reports latency."""
        start_time = time.perf_counter()
        try:
            client = await self.get_client()
            pong = await client.ping()
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "status": "healthy" if pong else "unhealthy",
                "connected": bool(pong),
                "latency_ms": latency_ms,
            }
        except Exception as e:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.warning(f"Redis health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "connected": False,
                "latency_ms": latency_ms,
                "error": str(e),
            }

    async def get(self, key: str) -> str | None:
        """Retrieves a string value by key."""
        try:
            client = await self.get_client()
            return await client.get(key)
        except Exception as e:
            logger.error(f"Redis get error for key '{key}': {str(e)}")
            return None

    async def set(self, key: str, value: str, expire_seconds: int | None = None) -> bool:
        """Sets a string value with optional expiration time."""
        try:
            client = await self.get_client()
            await client.set(key, value, ex=expire_seconds)
            return True
        except Exception as e:
            logger.error(f"Redis set error for key '{key}': {str(e)}")
            return False

    async def delete(self, key: str) -> bool:
        """Removes a key from Redis."""
        try:
            client = await self.get_client()
            res = await client.delete(key)
            return bool(res > 0)
        except Exception as e:
            logger.error(f"Redis delete error for key '{key}': {str(e)}")
            return False

    async def close(self) -> None:
        """Closes active Redis connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# Global singleton Redis service instance
redis_service = RedisService()
