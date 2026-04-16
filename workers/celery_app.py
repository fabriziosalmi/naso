from celery import Celery
import os
from .utils.tracing import setup_worker_tracing

# Inizializza Tracing prima della creazione dell'app Celery
setup_worker_tracing()

RABBITMQ_USER = os.getenv("RABBIT_USER", "naso_broker_admin")
RABBITMQ_PASS = os.getenv("RABBIT_PASSWORD", "change_me_rigorously")
RABBITMQ_HOST = os.getenv("RABBIT_HOST", "rabbitmq")

celery_app = Celery(
    "naso_workers",
    broker=f"pyamqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}//",
    include=["tasks.github", "tasks.pastes", "tasks.telegram", "tasks.pipeline", "tasks.maintenance"]
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
