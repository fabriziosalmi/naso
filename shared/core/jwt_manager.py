import redis.asyncio as redis

from shared.config import settings


class JWTBlacklist:
    def __init__(self):
        self.redis_client = None

    async def get_client(self):
        if self.redis_client is None:
            self.redis_client = redis.from_url(settings.REDIS_HOST, decode_responses=True)
        return self.redis_client

    async def blacklist_token(self, jti: str, expire_in_seconds: int):
        """Aggiunge il JTI alla blacklist con scadenza automatica misurata dal TTL residuo."""
        client = await self.get_client()
        if expire_in_seconds > 0:
            await client.setex(f"blacklist:{jti}", int(expire_in_seconds), "true")

    async def is_blacklisted(self, jti: str) -> bool:
        """Verifica istantanea se il JTI e compromesso/revocato."""
        if not jti:
            return False
        client = await self.get_client()
        exists = await client.exists(f"blacklist:{jti}")
        return exists > 0


jwt_blacklist = JWTBlacklist()
