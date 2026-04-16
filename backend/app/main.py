from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging
from shared.database import engine
from shared.config import settings

from .api.endpoints import auth, tenants, keywords, leaks, identities, yara, system, users, ai
from shared.utils.backend_tracing import setup_tracing
from shared.core.exceptions import NasoBaseException, AuthenticationError, AuthorizationError, ResourceNotFoundError

# Configurazione Logging Professionale
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
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
    openapi_url="/api/openapi.json"
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])

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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "127.0.0.1", "host.docker.internal", "naso-api"]
)
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
app.include_router(keywords.router, prefix="/keywords", tags=["keywords"])
app.include_router(leaks.router, prefix="/leaks", tags=["leaks"])
app.include_router(identities.router, prefix="/identities", tags=["identities"])
app.include_router(yara.router, prefix="/yara", tags=["yara"])
app.include_router(system.router, prefix="/system", tags=["system"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(ai.router, prefix="/ai", tags=["ai"])
