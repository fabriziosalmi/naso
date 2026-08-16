import os
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"

for path in (str(ROOT_DIR), str(BACKEND_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("JWT_PRIVATE_KEY", "test-secret")
os.environ.setdefault("JWT_PUBLIC_KEY", "test-secret")

# Models + DB session factory are lightweight (no FastAPI), so they stay at
# module scope and are always available to every test file. The FastAPI app
# and its dependencies (httpx, jwt_manager) are deferred to the ``client``
# fixture so the correlation-engine test files can run on a minimal install.
import contextlib

from shared.core.security import get_password_hash
from shared.database import get_db
from shared.models import Base, Tenant, User

# In-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _shared_engine_teardown():
    yield
    # aiosqlite runs each connection on its own non-daemon thread. Without
    # dispose() that thread outlives the suite and threading._shutdown blocks
    # forever, so pytest prints its summary and then never exits.
    await engine.dispose()


@pytest_asyncio.fixture
async def db_engine(_shared_engine_teardown):
    # Per test, not per session. The fixtures in test_api.py and test_auth.py
    # commit users with fixed email addresses, so a schema shared across the
    # whole run makes every test after the first fail on the UNIQUE index.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine


@pytest_asyncio.fixture
async def db(db_engine):
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db):
    # Deferred imports — the full FastAPI app is only needed when a test
    # actually exercises an HTTP endpoint. Correlation-engine tests can run
    # without these modules installed.
    from app.limiter import limiter
    from app.main import app
    from httpx import ASGITransport, AsyncClient

    from shared.core.jwt_manager import jwt_blacklist

    # /auth/login is capped at 10/minute and every request in the suite comes
    # from the same synthetic address, so the limiter starts returning 429
    # partway through the run and every later login assertion collapses.
    # Nothing here covers the HTTP rate limit — test_rate_limiter.py exercises
    # the dark-web TokenBucket, which is unrelated.
    limiter.enabled = False

    jwt_blacklist.is_blacklisted = AsyncMock(return_value=False)
    jwt_blacklist.blacklist_token = AsyncMock()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    # Must be a host that TrustedHostMiddleware accepts (see app/main.py).
    # The previous "http://test" produced a Host header the middleware
    # rejected, so every request in this suite came back 400 regardless of
    # what the test was asserting.
    async with AsyncClient(transport=transport, base_url="http://localhost") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db):
    """A single admin operator on a fresh tenant.

    Lives here rather than in test_auth.py because test_ai_agent.py needs it
    too, and a fixture defined in a test module is not visible to its siblings.
    """
    tenant = Tenant(name="Test TenantCorp")
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    user = User(
        email="operator@test.example.com",
        hashed_password=get_password_hash("securepass123"),
        tenant_id=tenant.id,
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ═══════════════════════════════════════════════════════════════════════════
# Correlation-engine fixtures
# ═══════════════════════════════════════════════════════════════════════════
#
# The correlation suite exercises concurrency (asyncio.gather across sessions)
# and schema-level constraints (UNIQUE, hash-chain). A shared in-memory
# SQLite serializes everything through a single connection, which would mask
# the very races we are trying to detect. Every correlation test therefore
# gets its own file-backed SQLite so we can open genuinely parallel sessions.


@pytest_asyncio.fixture
async def corr_engine():
    tmp = tempfile.NamedTemporaryFile(prefix="naso_corr_", suffix=".sqlite", delete=False)  # noqa: SIM115 — delete=False fixture; closed immediately, removed at teardown
    tmp.close()
    url = f"sqlite+aiosqlite:///{tmp.name}"
    eng = create_async_engine(url, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()
        with contextlib.suppress(FileNotFoundError):
            Path(tmp.name).unlink()


@pytest_asyncio.fixture
async def corr_session_factory(corr_engine):
    return sessionmaker(corr_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def corr_db(corr_session_factory):
    async with corr_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def tenant(corr_db):
    t = Tenant(id=str(uuid.uuid4()), name=f"test-tenant-{uuid.uuid4().hex[:8]}")
    corr_db.add(t)
    await corr_db.commit()
    await corr_db.refresh(t)
    return t


@pytest_asyncio.fixture
async def user(corr_db, tenant):
    u = User(
        id=str(uuid.uuid4()),
        email=f"op-{uuid.uuid4().hex[:6]}@naso.example.com",
        hashed_password="x",
        full_name="Test Operator",
        role="analyst",
        tenant_id=tenant.id,
    )
    corr_db.add(u)
    await corr_db.commit()
    await corr_db.refresh(u)
    return u
