"""Pool di connessione RabbitMQ condiviso a livello applicazione.

Usa una singola connessione robusta (auto-reconnect) e un canale per richiesta.
La connessione viene inizializzata al primo utilizzo e protetta con asyncio.Lock
per evitare race condition in contesti multi-coroutine.

Utilizzo:
    from app.infrastructure.rabbitmq import rabbitmq_pool
    channel = await rabbitmq_pool.get_channel()
    # usa il channel ...
    await channel.close()  # i canali sono leggeri e vanno chiusi dopo l'uso

Lifecycle:
    Chiamare `await rabbitmq_pool.close()` nello shutdown dell'app (lifespan).
"""

import asyncio
import logging

import aio_pika
import aio_pika.abc

from shared.config import settings

logger = logging.getLogger(__name__)


class _RabbitMQPool:
    """Singleton: una connessione robusta condivisa, canali usa-e-getta per richiesta."""

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
        """Ritorna un nuovo canale dalla connessione condivisa.

        Double-checked locking: la connessione viene creata una sola volta anche
        in presenza di molte coroutine concorrenti che chiamano get_channel
        simultaneamente all'avvio.
        """
        if self._connection is None or self._connection.is_closed:
            async with self._lock:
                # Seconda verifica dopo aver acquisito il lock (pattern DCL)
                if self._connection is None or self._connection.is_closed:
                    self._connection = await aio_pika.connect_robust(self._amqp_url)
                    logger.info("RabbitMQ: connessione robusta stabilita")

        return await self._connection.channel()

    async def close(self) -> None:
        """Chiude la connessione in modo ordinato durante lo shutdown dell'app."""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("RabbitMQ: connessione chiusa ordinatamente")


# Istanza globale — importata da leaks.py e dal lifespan di main.py
rabbitmq_pool = _RabbitMQPool()
