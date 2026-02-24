"""Test configuration and fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
def client() -> TestClient:
    """Provide a FastAPI TestClient for sync tests."""
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncClient:
    """Provide an async HTTP client using httpx."""
    client = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )
    yield client
    await client.aclose()
