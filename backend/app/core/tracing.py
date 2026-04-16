import os
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

def setup_tracing(app, engine):
    """
    Inizializza OpenTelemetry per il backend (#27).
    """
    otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://jaeger:4317")
    
    resource = Resource(attributes={
        SERVICE_NAME: "naso-backend"
    })
    
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Instrumentazione FastAPI
    FastAPIInstrumentor.instrument_app(app)
    
    # Instrumentazione SQLAlchemy
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    
    print("[NASO TRACING] Backend instrumentation complete.")
