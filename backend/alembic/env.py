"""Alembic env.py — async-compatible con asyncpg + SQLAlchemy 2.0

Supporta due modalità:
  - offline: genera SQL puro senza connessione al DB
  - online:  applica le migrazioni via connessione async
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Aggiungi la root del repo al path in modo che `shared` sia importabile
# sia dal container Docker che dall'ambiente di sviluppo locale.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.models import Base  # noqa: E402

# ── Configurazione Alembic ────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata di tutti i modelli: Alembic confronta questo schema con il DB
target_metadata = Base.metadata

# ── URL del database ──────────────────────────────────────────────────────────
# Legge DATABASE_URL dall'ambiente per non esporre credenziali in alembic.ini.
# Il formato asyncpg (postgresql+asyncpg://...) viene convertito in formato
# sincrono solo per la modalità offline, dove non serve un driver reale.
_database_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://naso:naso@db:5432/naso",
)
config.set_main_option("sqlalchemy.url", _database_url)


# ── Modalità OFFLINE ──────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Genera SQL senza connettersi al DB."""
    url = config.get_main_option("sqlalchemy.url")
    # asyncpg non supporta la modalità offline; usiamo il dialetto psycopg2
    offline_url = url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)
    context.configure(
        url=offline_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Modalità ONLINE (async) ────────────────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Crea un engine async e applica le migrazioni."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ── Entrypoint ────────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
