"""Tests for the uptime endpoint."""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from datetime import datetime
from http import HTTPStatus

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from src.core.config import settings
from src.uptime.router import router as uptime_router


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for uptime tests."""
    async with AsyncClient(
        transport=None,  # type: ignore[arg-type]
        base_url="http://test",
    ) as c:
        yield c


class TestUptimeEndpoint:
    """Tests for the GET /uptime endpoint."""

    @pytest.mark.asyncio
    async def test_uptime_returns_200(self) -> None:
        """Test that GET /uptime returns HTTP 200."""
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response = client.get("/uptime")

        assert response.status_code == HTTPStatus.OK

    @pytest.mark.asyncio
    async def test_uptime_response_has_exactly_three_fields(self) -> None:
        """Test that GET /uptime returns exactly the three required fields."""
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response = client.get("/uptime")
        data = response.json()

        expected_fields = {"service", "started_at", "uptime_seconds"}
        assert set(data.keys()) == expected_fields

    @pytest.mark.asyncio
    async def test_uptime_service_matches_app_name(self) -> None:
        """Test that service equals settings.app_name."""
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response = client.get("/uptime")
        data = response.json()

        assert data["service"] == settings.app_name

    @pytest.mark.asyncio
    async def test_uptime_started_at_is_iso8601_with_utc_offset(self) -> None:
        """Test that started_at parses as ISO-8601 with UTC offset."""
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response = client.get("/uptime")
        data = response.json()

        started_at_str = data["started_at"]
        # Parse the ISO-8601 string
        dt = datetime.fromisoformat(started_at_str)
        assert dt.tzinfo is not None, "started_at must have a timezone"
        assert dt.utcoffset() is not None, "started_at must have a UTC offset"

    @pytest.mark.asyncio
    async def test_uptime_uptime_seconds_is_float_and_non_negative(self) -> None:
        """Test that uptime_seconds is a float >= 0."""
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response = client.get("/uptime")
        data = response.json()

        assert isinstance(data["uptime_seconds"], float)
        assert data["uptime_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_uptime_started_at_is_stable_across_requests(self) -> None:
        """Test that started_at is the same value across two sequential requests."""
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response1 = client.get("/uptime")
        response2 = client.get("/uptime")

        data1 = response1.json()
        data2 = response2.json()

        assert data1["started_at"] == data2["started_at"]

    @pytest.mark.asyncio
    async def test_uptime_seconds_monotonically_increasing(self) -> None:
        """Test that uptime_seconds strictly increases between two requests."""
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response1 = client.get("/uptime")
        time.sleep(0.05)
        response2 = client.get("/uptime")

        data1 = response1.json()
        data2 = response2.json()

        assert data2["uptime_seconds"] > data1["uptime_seconds"]

    @pytest.mark.asyncio
    async def test_uptime_content_type(self) -> None:
        """Test that GET /uptime returns application/json content type."""
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response = client.get("/uptime")

        assert "application/json" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_uptime_post_not_allowed(self) -> None:
        """Test that POST /uptime returns 405 Method Not Allowed."""
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response = client.post("/uptime")

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    @pytest.mark.asyncio
    async def test_uptime_put_not_allowed(self) -> None:
        """Test that PUT /uptime returns 405 Method Not Allowed."""
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response = client.put("/uptime")

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    @pytest.mark.asyncio
    async def test_uptime_delete_not_allowed(self) -> None:
        """Test that DELETE /uptime returns 405 Method Not Allowed."""
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response = client.delete("/uptime")

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    @pytest.mark.asyncio
    async def test_uptime_patch_not_allowed(self) -> None:
        """Test that PATCH /uptime returns 405 Method Not Allowed."""
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response = client.patch("/uptime")

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
