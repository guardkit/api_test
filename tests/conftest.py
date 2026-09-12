"""Test configuration and fixtures."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from src.db.base import DeclarativeBase
from src.db.dependencies import get_db as app_get_db
from src.db.session import dispose_engine, init_engine
from src.main import app

# The in-memory database the tests have always used when nothing else is asked
# for. A developer who runs pytest with no environment set gets exactly this.
DEFAULT_TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def configured_database_url() -> str | None:
    """Return the database the tests were told to use, or None for the default.

    The suite of record (qa/run-suite.sh) starts a real PostgreSQL and puts its
    address in DATABASE_URL. When that variable is missing or empty, the tests
    use the in-memory SQLite database they have always used.

    Returns:
        str | None: The database address, or None when none was given.
    """
    value = os.environ.get("DATABASE_URL", "").strip()
    return value or None


def _where_it_points(database_url: str) -> str:
    """Describe a database address for a person, without its password.

    Args:
        database_url: The address the tests were told to use.

    Returns:
        str: A plain phrase naming the host and the port.
    """
    url = make_url(database_url)
    host = url.host or "(no host in the address)"
    port = url.port if url.port is not None else "(the driver's default port)"
    return f"host {host} port {port}"


def _cannot_be_reached(database_url: str, reason: BaseException) -> None:
    """Stop the run with a plain sentence naming the server that is missing.

    The tests never quietly fall back to SQLite when a real database was asked
    for: that is precisely the blindness this harness exists to remove.

    Args:
        database_url: The address the tests were told to use.
        reason: The error the database driver raised.

    Raises:
        Failed: Always. The test that asked for the database fails.
    """
    url = make_url(database_url)
    pytest.fail(
        "The tests were told to use the database at "
        f"{_where_it_points(database_url)} "
        f"({url.render_as_string(hide_password=True)}), and that server could "
        f"not be reached: {type(reason).__name__}: {reason}. The tests do not "
        "fall back to the in-memory SQLite database, because a test that "
        "passes against the wrong database proves nothing. Start the server, "
        "or unset DATABASE_URL to test against in-memory SQLite on purpose.",
        pytrace=False,
    )


def _search_path_connect_args(schema: str, database_url: str) -> dict[str, object]:
    """Build the connection settings that put a test in its own schema.

    Args:
        schema: The name of the schema made for this one test.
        database_url: The address the tests were told to use.

    Returns:
        dict[str, object]: Connection settings for this database's driver.

    Raises:
        Failed: When the driver is one this harness has never been taught.
    """
    driver = make_url(database_url).get_driver_name()
    if driver == "asyncpg":
        return {"server_settings": {"search_path": f"{schema},public"}}
    if driver in {"psycopg", "psycopg2"}:
        return {"options": f"-csearch_path={schema},public"}
    pytest.fail(
        f"The tests were told to use a PostgreSQL database through the "
        f"'{driver}' driver, which this test harness does not know how to give "
        "each test its own schema with. Use asyncpg (the driver the "
        "application itself uses), or unset DATABASE_URL to test against "
        "in-memory SQLite.",
        pytrace=False,
    )
    raise AssertionError("unreachable")  # pragma: no cover


@asynccontextmanager
async def database_engine_for_one_test(
    database_url: str | None,
) -> AsyncIterator[AsyncEngine]:
    """Open the engine one test runs against, and clean up after it.

    With no address given, this is the in-memory SQLite engine the tests have
    always used: it is created, the tables are made in it, and it disappears
    with the test.

    With an address given, the engine points at that server, and the test is
    kept apart from every other test by a schema of its own: a schema with a
    name nobody else can guess is created, the tables are made inside it, and
    the whole schema is dropped when the test ends. Because the suite runs each
    test in its own process (pytest --forked), two tests running at the same
    time each get their own schema and cannot see each other's rows.

    Args:
        database_url: The address to use, or None for in-memory SQLite.

    Yields:
        AsyncEngine: The engine for this one test, with the tables in place.
    """
    if database_url is None:
        engine = create_async_engine(
            DEFAULT_TEST_DATABASE_URL,
            echo=False,
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(DeclarativeBase.metadata.create_all)
        try:
            yield engine
        finally:
            async with engine.begin() as conn:
                await conn.run_sync(DeclarativeBase.metadata.drop_all)
            await engine.dispose()
        return

    url = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        # A SQLite file or memory database named on purpose: no schemas to make,
        # so the tables are created and dropped around the test instead.
        engine = create_async_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
        try:
            async with engine.begin() as conn:
                await conn.run_sync(DeclarativeBase.metadata.create_all)
        except Exception as reason:  # pragma: no cover - a bad path or file
            await engine.dispose()
            _cannot_be_reached(database_url, reason)
        try:
            yield engine
        finally:
            async with engine.begin() as conn:
                await conn.run_sync(DeclarativeBase.metadata.drop_all)
            await engine.dispose()
        return

    schema = f"test_{uuid.uuid4().hex}"
    engine = create_async_engine(
        database_url,
        echo=False,
        connect_args=_search_path_connect_args(schema, database_url),
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    except Exception as reason:
        await engine.dispose()
        _cannot_be_reached(database_url, reason)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(DeclarativeBase.metadata.create_all)
        yield engine
    finally:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            await engine.dispose()


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Provide the database engine for one test, with the tables in place.

    With DATABASE_URL set (the suite of record sets it to a real PostgreSQL),
    the engine points at that server and the test runs in a schema of its own.
    With DATABASE_URL unset, the engine is the in-memory SQLite one the tests
    have always used. If DATABASE_URL is set and the server cannot be reached,
    the test fails saying so; it never falls back to SQLite.

    Yields:
        AsyncEngine: Engine for this test, with the schema already created.
    """
    async with database_engine_for_one_test(configured_database_url()) as engine:
        yield engine


@pytest.fixture
async def db_session(
    db_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Create an async database session with per-test transaction rollback.

    This fixture starts a transaction, yields a session, and rolls back
    the transaction after the test completes to ensure test isolation.

    Args:
        db_engine: The async database engine fixture.

    Yields:
        AsyncSession: A database session for the current test.
    """
    async with db_engine.begin() as conn:
        # Create session factory bound to connection
        async_session_factory = sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with async_session_factory() as session:
            yield session


@pytest.fixture
async def override_get_db(
    db_session: AsyncSession,
) -> AsyncGenerator[None, None]:
    """Override the get_db dependency on the FastAPI app.

    This fixture replaces the app's get_db dependency with a test provider
    that yields the test database session.

    Args:
        db_session: The async database session fixture.

    Yields:
        None: After the test completes, the dependency override is removed.
    """
    # Override the dependency
    async def test_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[app_get_db] = test_get_db

    yield

    # Remove override after test
    if app_get_db in app.dependency_overrides:
        del app.dependency_overrides[app_get_db]


@pytest.fixture
def client() -> TestClient:
    """Provide a FastAPI TestClient for sync tests.

    Returns:
        TestClient: Configured test client without dependency override.
    """
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client using httpx.

    Yields:
        AsyncClient: Configured async client without dependency override.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
