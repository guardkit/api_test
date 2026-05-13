"""Test configuration and fixtures."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
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


@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create async SQLite in-memory engine with schema setup.

    This fixture creates a test database engine and sets up the schema
    using create_all(). The schema is torn down after all tests complete.

    Yields:
        AsyncEngine: Configured async SQLite engine with schema initialized.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(DeclarativeBase.metadata.create_all)

    yield engine

    # Drop all tables on teardown
    async with engine.begin() as conn:
        await conn.run_sync(DeclarativeBase.metadata.drop_all)

    await engine.dispose()


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
