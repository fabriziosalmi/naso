import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Sentry: importato solo se SENTRY_DSN è configurato — evita init inconsistente (G-14)
_sentry_enabled = bool(os.environ.get("SENTRY_DSN"))
if _sentry_enabled:
    import sentry_sdk

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        profiles_sample_rate=float(os.environ.get("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
        environment=os.environ.get("ENVIRONMENT", "production"),
    )

from shared.config import settings
from shared.database import engine

from .api.endpoints import ai, auth, identities, keywords, leaks, sec, system, tenants, users, yara
from .csrf import CSRFMiddleware
from .infrastructure.rabbitmq import rabbitmq_pool
from .limiter import limiter

# Logging configuration
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
    await rabbitmq_pool.close()
    await engine.dispose()
    logger.info("System safely shut down. Async resources released.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="NASO Forensic Engine API - High-performance intelligence framework for real-time threat intelligence and identity correlation.",
    version="0.1.1",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    default_response_class=ORJSONResponse,
)

# Rate limiter: esponi come stato app e registra handler 429
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth.router, prefix="/auth", tags=["auth"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global Exception Caught: {exc}")
    if _sentry_enabled:
        import sentry_sdk  # noqa: PLC0415 — cached import, always free after first load

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


# CSRF (double-submit cookie), registered BEFORE CORS. Starlette applies
# middleware in reverse registration order, so CORS ends up more external and
# can answer a preflight OPTIONS without the CSRF check ever running.
app.add_middleware(CSRFMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.ALLOWED_CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # Explicit headers: a "*" wildcard accepts any custom header, bypassing WAF
    # and proxy rules (G-05).
    allow_headers=[
        "Accept",
        "Authorization",
        "Content-Type",
        "X-Requested-With",
        "X-CSRF-Token",
        "X-Naso-CSRF",
        "Cache-Control",
    ],
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
app.include_router(sec.router, prefix="/api/v1/sec", tags=["sec"])
