from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from .database import engine
from .config import settings
from .api.endpoints import auth, tenants, keywords, leaks, identities, yara, system
from .core.tracing import setup_tracing
from .core.exceptions import NasoBaseException, AuthenticationError, AuthorizationError, ResourceNotFoundError

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

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
app.include_router(keywords.router, prefix="/keywords", tags=["keywords"])
app.include_router(leaks.router, prefix="/leaks", tags=["leaks"])
app.include_router(identities.router, prefix="/identities", tags=["identities"])
app.include_router(yara.router, prefix="/yara", tags=["yara"])
app.include_router(system.router, prefix="/system", tags=["system"])
