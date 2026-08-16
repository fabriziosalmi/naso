import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.elasticsearch import ElasticsearchInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_TRUTHY = {"1", "true", "yes", "on"}


def is_enabled() -> bool:
    """Whether OTLP export is switched on.

    Same ``NASO_OTEL_ENABLED`` toggle as ``shared.utils.tracing``, and the
    same default: off. Installing a BatchSpanProcessor unconditionally means
    every process that merely imports this module acquires an exporter that
    retries against ``OTLP_ENDPOINT`` on shutdown — which blocks process exit
    when nothing is listening there. The Compose stack sets the variable, so
    the development deployment still traces to Jaeger.

    Read at call time rather than import time so tests can toggle it.
    """
    return os.getenv("NASO_OTEL_ENABLED", "").strip().lower() in _TRUTHY


def setup_worker_tracing(engine=None):
    if not is_enabled():
        return

    otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://host.docker.internal:4318/v1/traces")
    resource = Resource(attributes={SERVICE_NAME: "naso-worker"})
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    CeleryInstrumentor().instrument()
    ElasticsearchInstrumentor().instrument()
    if engine:
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    print("[NASO TRACING] Worker instrumentation complete.")
