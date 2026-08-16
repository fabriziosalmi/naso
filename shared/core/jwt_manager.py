import asyncio

import redis.asyncio as redis

from shared.config import settings


class JWTBlacklist:
    def __init__(self):
        self._redis_client = None
        # asyncio lock guarding the lazy init against concurrent coroutines
        self._lock = asyncio.Lock()

    async def get_client(self):
        # Fast path without the lock — avoids overhead on the vast majority of calls
        if self._redis_client is not None:
            return self._redis_client
        # Slow path: take the lock and initialise exactly once (double-checked locking)
        async with self._lock:
            if self._redis_client is None:
                self._redis_client = redis.from_url(settings.REDIS_HOST, decode_responses=True)
        return self._redis_client

    async def blacklist_token(self, jti: str, expire_in_seconds: int):
        """Blacklist the JTI, expiring automatically after the token's remaining TTL."""
        client = await self.get_client()
        if expire_in_seconds > 0:
            await client.setex(f"blacklist:{jti}", int(expire_in_seconds), "true")

    async def is_blacklisted(self, jti: str) -> bool:
        """Constant-time check for whether the JTI has been revoked."""
        if not jti:
            return False
        client = await self.get_client()
        exists = await client.exists(f"blacklist:{jti}")
        return exists > 0


jwt_blacklist = JWTBlacklist()
