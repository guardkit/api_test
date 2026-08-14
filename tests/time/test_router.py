"""Tests for the time endpoint router."""

from __future__ import annotations

import re
from http import HTTPStatus

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_time_endpoint_returns_200(async_client: AsyncClient) -> None:
    """AC-001: GET /time returns HTTP 200."""
    response = await async_client.get("/time")

    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_time_endpoint_exactly_two_fields(async_client: AsyncClient) -> None:
    """AC-001: GET /time returns exactly two fields: time and service."""
    response = await async_client.get("/time")
    data = response.json()

    assert set(data.keys()) == {"time", "service"}


@pytest.mark.asyncio
async def test_time_endpoint_time_format(async_client: AsyncClient) -> None:
    """AC-002: time is current UTC in ISO-8601 second precision with trailing Z."""
    response = await async_client.get("/time")
    data = response.json()

    time_str = data["time"]

    # Must end with Z
    assert time_str.endswith("Z"), f"time must end with Z, got: {time_str}"

    # ISO-8601 second precision pattern: YYYY-MM-DDTHH:MM:SSZ
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
    assert re.match(pattern, time_str), f"time does not match ISO-8601 second precision: {time_str}"

    # No microseconds (second precision)
    assert "." not in time_str, "time must not contain microseconds"


@pytest.mark.asyncio
async def test_time_endpoint_service_value(async_client: AsyncClient) -> None:
    """AC-002: service is 'api_test'."""
    response = await async_client.get("/time")
    data = response.json()

    assert data["service"] == "api_test"


@pytest.mark.asyncio
async def test_time_endpoint_freshness(async_client: AsyncClient) -> None:
    """AC-003: Two GET /time calls at least one second apart return strictly increasing timestamps."""
    response1 = await async_client.get("/time")
    data1 = response1.json()

    # Wait at least 1 second
    import asyncio
    await asyncio.sleep(1.1)

    response2 = await async_client.get("/time")
    data2 = response2.json()

    # Parse timestamps (remove Z, add +00:00 for parsing)
    from datetime import datetime, timezone

    t1 = datetime.fromisoformat(data1["time"].replace("Z", "+00:00"))
    t2 = datetime.fromisoformat(data2["time"].replace("Z", "+00:00"))

    assert t2 > t1, f"Timestamps must be strictly increasing: {data1['time']} vs {data2['time']}"


@pytest.mark.asyncio
async def test_time_endpoint_post_returns_405(async_client: AsyncClient) -> None:
    """AC-004: POST /time returns 405 Method Not Allowed."""
    response = await async_client.post("/time")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.asyncio
async def test_time_endpoint_put_returns_405(async_client: AsyncClient) -> None:
    """AC-004: PUT /time returns 405 Method Not Allowed."""
    response = await async_client.put("/time")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.asyncio
async def test_time_endpoint_delete_returns_405(async_client: AsyncClient) -> None:
    """AC-004: DELETE /time returns 405 Method Not Allowed."""
    response = await async_client.delete("/time")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.asyncio
async def test_time_endpoint_no_database_required(async_client: AsyncClient) -> None:
    """AC-005: The route returns 200 with no database available (bare TestClient).

    This test exercises the /time route directly without any database fixture.
    The route must work independently of database connectivity.
    """
    response = await async_client.get("/time")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert "time" in data
    assert "service" in data
    assert set(data.keys()) == {"time", "service"}


@pytest.mark.asyncio
async def test_time_endpoint_content_type(async_client: AsyncClient) -> None:
    """Verify the response has application/json content type."""
    response = await async_client.get("/time")

    assert "application/json" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_time_router_no_db_imports() -> None:
    """AC-005: The time router imports nothing from src/db.

    Verify that src/time/router.py does not contain any imports from src.db.
    """
    import importlib
    import inspect

    # Import the router module
    from src.time import router as time_router_module

    # Get the source code of the module
    source = inspect.getsource(time_router_module)

    # Check that there are no imports from src.db
    assert "from src.db" not in source, (
        "src/time/router.py must not import from src.db"
    )
    assert "import src.db" not in source, (
        "src/time/router.py must not import src.db"
    )
