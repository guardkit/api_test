"""Tests for the uptime endpoint."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime
from http import HTTPStatus
from pathlib import Path

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
    async def test_uptime_sequential_requests_increasing_uptime(self) -> None:
        """Test that two sequential requests show increasing uptime_seconds."""
        import time

        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response1 = client.get("/uptime")
        data1 = response1.json()

        time.sleep(0.05)

        response2 = client.get("/uptime")
        data2 = response2.json()

        assert data2["uptime_seconds"] > data1["uptime_seconds"]

    @pytest.mark.asyncio
    async def test_uptime_started_at_identical_across_requests(self) -> None:
        """Test that started_at is identical in two sequential requests."""
        import time

        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response1 = client.get("/uptime")
        data1 = response1.json()

        time.sleep(0.05)

        response2 = client.get("/uptime")
        data2 = response2.json()

        assert data1["started_at"] == data2["started_at"]

    @pytest.mark.asyncio
    async def test_uptime_post_returns_405(self) -> None:
        """Test that POST /uptime returns 405 Method Not Allowed."""
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(uptime_router)
        client = TestClient(app)

        response = client.post("/uptime")

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


class TestUptimeSchema:
    """Tests for the UptimeResponse schema."""

    def test_uptime_response_has_json_schema_extra(self) -> None:
        """Test that UptimeResponse includes json_schema_extra with examples."""
        from src.uptime.schemas import UptimeResponse

        examples = UptimeResponse.model_config["json_schema_extra"]["examples"]

        assert isinstance(examples, list)
        assert len(examples) >= 1

        example = examples[0]
        assert "service" in example
        assert "started_at" in example
        assert "uptime_seconds" in example

    def test_uptime_response_has_field_descriptions(self) -> None:
        """Test that UptimeResponse fields have descriptions."""
        from src.uptime.schemas import UptimeResponse

        schema = UptimeResponse.model_json_schema()

        for field_name in ("service", "started_at", "uptime_seconds"):
            assert field_name in schema["properties"]
            assert "description" in schema["properties"][field_name]

    def test_uptime_response_field_types(self) -> None:
        """Test that UptimeResponse has correct field types."""
        from src.uptime.schemas import UptimeResponse

        schema = UptimeResponse.model_json_schema()

        assert schema["properties"]["service"]["type"] == "string"
        assert schema["properties"]["started_at"]["type"] == "string"
        assert schema["properties"]["started_at"]["format"] == "date-time"
        assert schema["properties"]["uptime_seconds"]["type"] == "number"


class TestUptimeNoDatabaseCoupling:
    """Test that the uptime module has no database coupling."""

    def test_uptime_no_db_import(self) -> None:
        """Test that src/uptime/ contains no import of src.db."""
        uptime_dir = Path(__file__).parent.parent.parent / "src" / "uptime"

        for py_file in uptime_dir.glob("*.py"):
            content = py_file.read_text()
            # Check for any import of src.db or from src.db
            assert "src.db" not in content, (
                f"{py_file.name} contains a reference to src.db"
            )

    def test_uptime_router_no_db_dependency(self) -> None:
        """Test that the uptime router does not import database dependencies."""
        from src.uptime import router as uptime_router_module

        source = uptime_router_module.__file__
        with open(source) as f:
            content = f.read()

        assert "from src.db" not in content, "router.py must not import from src.db"
        assert "import src.db" not in content, "router.py must not import src.db"


class TestUptimeRouterRegistration:
    """Test that the uptime router is properly registered in main.py."""

    def test_uptime_tag_in_openapi(self) -> None:
        """Test that the uptime tag is registered in the OpenAPI schema."""
        from src.main import app

        openapi_tags = app.openapi_tags
        assert openapi_tags is not None

        uptime_tag = None
        for tag in openapi_tags:
            if tag["name"] == "uptime":
                uptime_tag = tag
                break

        assert uptime_tag is not None, "uptime tag must be in openapi_tags"
        assert "description" in uptime_tag

    def test_uptime_endpoint_in_openapi_paths(self) -> None:
        """Test that GET /uptime is in the OpenAPI paths."""
        from src.main import app

        openapi_schema = app.openapi()
        assert "/uptime" in openapi_schema["paths"]
        assert "get" in openapi_schema["paths"]["/uptime"]
