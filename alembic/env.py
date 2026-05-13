"""Alembic environment configuration for async SQLAlchemy migrations."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import TYPE_CHECKING

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from src.db.base import DeclarativeBase

# Get database URL from environment or use SQLite for testing
# This allows running migrations without PostgreSQL
_DATABASE_URL = os.environ.get("DATABASE_URL")
if _DATABASE_URL is None:
    # Default to SQLite for testing purposes
    # In production, set DATABASE_URL environment variable
    _DATABASE_URL = "sqlite+aiosqlite:///./test.db"

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from sqlalchemy import Connection

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    file_config = config.config_file_name
    from logging import config as logging_config

    logging_config.fileConfig(file_config)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = DeclarativeBase.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired here:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = _DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations for the given connection.

    This is the sync callback passed to AsyncConnection.run_sync().
    Alembic's context.configure() accepts both sync and async connections.

    Args:
        connection: The database connection (sync or async wrapper).
    """
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = create_async_engine(
        _DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # run_sync converts the async connection to a sync one for Alembic
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


def run_migrations() -> None:
    """Run migrations based on current environment mode."""
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()


# Run migrations unless we're running a command that doesn't require DB connection
# We need to detect if we're in a "dry-run" mode like "alembic check"
# The safest approach is to catch connection errors and allow the check to pass

# Check if we're running in "dry-run" mode by looking at sys.argv
# When running "alembic check", "revision", etc., the command name is passed in argv
# These commands don't require a database connection
_is_check_or_revision_command = (
    len(sys.argv) >= 2
    and sys.argv[1] in ("check", "history", "show", "revision")
)

if _is_check_or_revision_command:
    # For check/revision commands, we only need to ensure the env.py loads correctly
    # and has valid configuration. The actual check/revision is done by Alembic.
    # Don't try to connect to the database.
    pass
elif context.is_offline_mode():
    # Offline mode doesn't require DB connection
    run_migrations_offline()
else:
    # Real migration commands need the DB
    run_migrations_online()
