"""Application-wide shared RabbitMQ connection pool.

Uses a single robust connection (auto-reconnect) and one channel per request.
The connection is initialised on first use and guarded by an asyncio.Lock to
avoid a race between concurrent coroutines.

Utilizzo:
    from app.infrastructure.rabbitmq import rabbitmq_pool
    channel = await rabbitmq_pool.get_channel()
    # use the channel ...
    await channel.close()  # channels are cheap and should be closed after use

Lifecycle:
    Call `await rabbitmq_pool.close()` on application shutdown (lifespan).
"""

import asyncio
import logging

import aio_pika
import aio_pika.abc

from shared.config import settings

logger = logging.getLogger(__name__)


class _RabbitMQPool:
    """Singleton: one shared robust connection, throwaway channels per request."""

    def __init__(self) -> None:
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._lock = asyncio.Lock()

    @property
    def _amqp_url(self) -> str:
        user = settings.RABBITMQ_USER or ""
        passwd = settings.RABBITMQ_PASS or ""
        host = settings.RABBITMQ_HOST
        return f"amqp://{user}:{passwd}@{host}/"

    async def get_channel(self) -> aio_pika.abc.AbstractChannel:
        """Return a new channel from the shared connection.

        Double-checked locking: the connection is created exactly once even when
        many concurrent coroutines call get_channel
        at startup.
        """
        if self._connection is None or self._connection.is_closed:
            async with self._lock:
                # Second check after acquiring the lock (DCL pattern)
                if self._connection is None or self._connection.is_closed:
                    self._connection = await aio_pika.connect_robust(self._amqp_url)
                    logger.info("RabbitMQ: robust connection established")

        return await self._connection.channel()

    async def close(self) -> None:
        """Close the connection cleanly during application shutdown."""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("RabbitMQ: connection closed cleanly")


# Global instance — imported by leaks.py and by the lifespan in main.py
rabbitmq_pool = _RabbitMQPool()
