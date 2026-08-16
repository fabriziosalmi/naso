"""Alembic env.py — async-compatible with asyncpg + SQLAlchemy 2.0

Supporta due modalità:
  - offline: emit raw SQL without connecting to the database
  - online:  apply the migrations over an async connection
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Put the repo root on the path so `shared` is importable both from the
# Docker container and from a local development environment.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.models import Base  # noqa: E402

# ── Alembic configuration ────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for every model: Alembic diffs this schema against the database
target_metadata = Base.metadata

# ── Database URL ──────────────────────────────────────────────────────────
# Read DATABASE_URL from the environment so credentials never land in
# alembic.ini. The asyncpg form (postgresql+asyncpg://...) is converted to a
# sync URL for offline mode only, where no real driver is needed.
_database_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://naso:naso@db:5432/naso",
)
config.set_main_option("sqlalchemy.url", _database_url)


# ── Modalità OFFLINE ──────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Emit SQL without connecting to the database."""
    url = config.get_main_option("sqlalchemy.url")
    # asyncpg has no offline mode; use the psycopg2 dialect instead
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
    """Create an async engine and run the migrations."""
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
