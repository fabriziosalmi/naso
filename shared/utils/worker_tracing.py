import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.elasticsearch import ElasticsearchInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_worker_tracing(engine=None):
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
