import asyncio
import logging
import time
from enum import Enum

logger = logging.getLogger("naso-circuit-breaker")


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30, name="default"):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time = None

    async def __call__(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.warning(f"[CIRCUIT BREAKER] {self.name} attempting recovery (HALF-OPEN)")
            else:
                raise Exception(f"Circuit Breaker {self.name} is OPEN. Blocking request.")

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                # Wrap sync calls if necessary, though we prefer async
                result = func(*args, **kwargs)

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failures = 0
                logger.info(f"[CIRCUIT BREAKER] {self.name} recovered (CLOSED)")

            # Reset failures on success if CLOSED (optional, depends on policy)
            # self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()

            if self.failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(
                    f"[CIRCUIT BREAKER] {self.name} opened after {self.failures} failures. Last error: {str(e)}"
                )

            raise e


# Singletons for common services
es_breaker = CircuitBreaker(name="Elasticsearch", failure_threshold=3, recovery_timeout=60)
minio_breaker = CircuitBreaker(name="MinIO", failure_threshold=3, recovery_timeout=60)
