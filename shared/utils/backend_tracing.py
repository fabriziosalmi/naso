import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_TRUTHY = {"1", "true", "yes", "on"}


def is_enabled() -> bool:
    """Whether OTLP export is switched on — see ``shared.utils.worker_tracing``
    for why this defaults to off. The Compose stack sets ``NASO_OTEL_ENABLED``,
    so the development deployment still traces to Jaeger.
    """
    return os.getenv("NASO_OTEL_ENABLED", "").strip().lower() in _TRUTHY


def setup_tracing(app, engine):
    if not is_enabled():
        return

    otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://host.docker.internal:4318/v1/traces")
    resource = Resource(attributes={SERVICE_NAME: "naso-backend"})
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    print("[NASO TRACING] Backend instrumentation complete.")
