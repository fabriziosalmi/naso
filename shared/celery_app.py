from celery import Celery
import os
from shared.utils.worker_tracing import setup_worker_tracing

# Inizializza Tracing prima della creazione dell'app Celery
setup_worker_tracing()

RABBITMQ_USER = os.getenv("RABBIT_USER", "naso_broker_admin")
RABBITMQ_PASS = os.getenv("RABBIT_PASSWORD", "rigorous_admin_password_2026")
RABBITMQ_HOST = os.getenv("RABBIT_HOST", "rabbitmq")

celery_app = Celery(
    "naso_workers",
    broker=f"pyamqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}//",
    include=["shared.tasks.github", "shared.tasks.pastes", "shared.tasks.telegram", "shared.tasks.pipeline", "shared.tasks.maintenance"]
)

celery_app.conf.update(
    result_expires=3600,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Backpressure & Bulkhead (#16, #18)
    worker_prefetch_multiplier=1, # Evita accumulo di task nel worker
    task_acks_late=True, # Ack solo a task completato
    worker_concurrency=4, # Numero di processi paralleli (ottimizzato per core Mac)
    task_time_limit=300, # Hard limit 5 min
)
