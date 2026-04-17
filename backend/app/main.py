import logging
import sentry_sdk
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

sentry_sdk.init(
    dsn="https://00000000000000000000000000000000@o0.ingest.sentry.io/0",  # Fake Mock DSN
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
    environment="production"
)

from shared.config import settings
from shared.database import engine

from .api.endpoints import ai, auth, identities, keywords, leaks, system, tenants, users, yara

# Configurazione Logging Professionale
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("naso-core")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"System {settings.PROJECT_NAME} starting up with Async Core...")
    yield
    # Shutdown
    await engine.dispose()
    logger.info("System safely shut down. Async resources released.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="NASO Forensic Engine API - High-performance intelligence framework for real-time threat intelligence and identity correlation.",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    default_response_class=ORJSONResponse,
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global Exception Caught: {exc}")
    sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "A critical system error occurred. Telemetry has logged the payload."},
    )


@app.middleware("http")
async def secure_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.ALLOWED_CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "host.docker.internal", "naso-api"])
app.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
app.include_router(keywords.router, prefix="/keywords", tags=["keywords"])
app.include_router(leaks.router, prefix="/leaks", tags=["leaks"])
app.include_router(identities.router, prefix="/identities", tags=["identities"])
app.include_router(yara.router, prefix="/yara", tags=["yara"])
app.include_router(system.router, prefix="/system", tags=["system"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(ai.router, prefix="/ai", tags=["ai"])
