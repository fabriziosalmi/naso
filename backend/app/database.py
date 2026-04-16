from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from .config import settings

# Engine asincrono centralizzato
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=int(settings.dict().get("DB_POOL_SIZE", 50)),
    max_overflow=int(settings.dict().get("DB_MAX_OVERFLOW", 100)),
    pool_timeout=10,
    pool_recycle=1800,
    pool_pre_ping=True,
    connect_args={
        "prepared_statement_cache_size": 500,
        "statement_cache_size": 1000
    },
    echo=False
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
