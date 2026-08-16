from celery import Celery
from celery.signals import worker_init

from shared.config import settings
from shared.utils.worker_tracing import setup_worker_tracing

# Initialise tracing before the Celery app is created
setup_worker_tracing()


@worker_init.connect
def _require_broker_credentials(**_):
    """Refuse to start a worker without broker credentials.

    This check used to run at module import, which meant that merely
    importing the Celery app — as the API does, and as every unit test that
    touches the FastAPI app does transitively — raised unless RabbitMQ was
    configured. Binding it to ``worker_init`` keeps the fail-fast exactly
    where it matters (a worker booting against a misconfigured broker) while
    leaving imports side-effect free.
    """
    if not settings.RABBITMQ_USER or not settings.RABBITMQ_PASS:
        raise ValueError("CRITICAL: RABBITMQ credentials missing in config/env!")


celery_app = Celery(
    "naso_workers",
    broker=f"pyamqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASS}@{settings.RABBITMQ_HOST}//",
    include=[
        "shared.tasks.github",
        "shared.tasks.pastes",
        "shared.tasks.telegram",
        "shared.tasks.pipeline",
        "shared.tasks.maintenance",
        "shared.tasks.darkweb",
        "shared.tasks.infrastructure",
        "shared.tasks.massive",
    ],
)

celery_app.conf.update(
    result_expires=3600,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Backpressure & Bulkhead (#16, #18)
    worker_prefetch_multiplier=1,  # Prevents tasks piling up inside a worker
    task_acks_late=True,  # Ack solo a task completato
    worker_concurrency=4,  # Number of parallel worker processes
    task_time_limit=300,  # Hard limit 5 min
    task_routes={
        "tasks.massive.*": {"queue": "massive"},
        "tasks.infrastructure.*": {"queue": "osint"},
        "tasks.darkweb.*": {"queue": "osint"},
        "*": {"queue": "default"},
    },
)
