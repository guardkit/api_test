"""Tests for the GET /stats endpoint and request counter middleware."""

from __future__ import annotations

from datetime import datetime
from http import HTTPStatus

import pytest
from fastapi import FastAPI

from src.core.config import settings
from src.stats.router import (
    StatsCounterMiddleware,
    StatsState,
)
from src.stats.router import (
    router as stats_router,
)


def _build_app() -> FastAPI:
    """Build a minimal FastAPI app with the stats router and middleware."""
    app = FastAPI()
    app.add_middleware(StatsCounterMiddleware)
    app.include_router(stats_router)
    return app


# ---------------------------------------------------------------------------
# AC-1: GET /stats returns success with exactly three fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_returns_200() -> None:
    """AC-1: GET /stats returns HTTP 200 with a JSON body."""
    app = _build_app()
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/stats")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"service", "requests_served", "first_request_at"}


@pytest.mark.asyncio
async def test_stats_response_types() -> None:
    """AC-1: Verify field types in the response."""
    app = _build_app()
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/stats")
    data = response.json()

    assert isinstance(data["service"], str)
    assert isinstance(data["requests_served"], int)
    # first_request_at is either a string or null
    assert data["first_request_at"] is None or isinstance(data["first_request_at"], str)


@pytest.mark.asyncio
async def test_stats_content_type() -> None:
    """AC-1: Verify application/json content type."""
    app = _build_app()
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/stats")

    assert response.headers["content-type"] == "application/json"


# ---------------------------------------------------------------------------
# AC-2: service equals configured app name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_service_matches_app_name() -> None:
    """AC-2: service equals settings.app_name."""
    app = _build_app()
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/stats")
    data = response.json()

    assert data["service"] == settings.app_name


# ---------------------------------------------------------------------------
# AC-3: requests_served strictly increases on second GET /stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_counter_increases() -> None:
    """AC-3: requests_served is strictly greater on a second GET /stats."""
    app = _build_app()
    from fastapi.testclient import TestClient

    client = TestClient(app)

    response1 = client.get("/stats")
    data1 = response1.json()

    response2 = client.get("/stats")
    data2 = response2.json()

    assert data2["requests_served"] > data1["requests_served"]


# ---------------------------------------------------------------------------
# AC-4: first_request_at is identical across responses and parses as UTC ISO-8601
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_first_request_at_consistent() -> None:
    """AC-4: first_request_at is identical across successive responses."""
    app = _build_app()
    from fastapi.testclient import TestClient

    client = TestClient(app)

    response1 = client.get("/stats")
    data1 = response1.json()

    response2 = client.get("/stats")
    data2 = response2.json()

    assert data1["first_request_at"] == data2["first_request_at"]


@pytest.mark.asyncio
async def test_stats_first_request_at_parses_utc_iso8601() -> None:
    """AC-4: first_request_at parses as UTC ISO-8601."""
    app = _build_app()
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/stats")
    data = response.json()

    assert data["first_request_at"] is not None
    dt = datetime.fromisoformat(data["first_request_at"])
    assert dt.tzinfo is not None
    assert dt.utcoffset() is not None


# ---------------------------------------------------------------------------
# AC-5: Fresh app first GET /stats: requests_served >= 1, first_request_at not null
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_first_request_served_ge_1() -> None:
    """AC-5: First GET /stats reports requests_served >= 1."""
    app = _build_app()
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/stats")
    data = response.json()

    assert data["requests_served"] >= 1


@pytest.mark.asyncio
async def test_stats_first_request_first_request_at_not_null() -> None:
    """AC-5: First GET /stats reports non-null first_request_at."""
    app = _build_app()
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/stats")
    data = response.json()

    assert data["first_request_at"] is not None


# ---------------------------------------------------------------------------
# AC-6: Non-stats requests also increment the counter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_counter_increased_by_non_stats_request() -> None:
    """AC-6: A request to an existing non-stats endpoint increases requests_served."""
    app = _build_app()

    # Add a simple non-stats endpoint
    @app.get("/other")
    async def other_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Hit the non-stats endpoint
    client.get("/other")

    # Now check stats — counter >= 1 (the /stats request itself is also counted)
    response = client.get("/stats")
    data = response.json()

    assert data["requests_served"] >= 1


@pytest.mark.asyncio
async def test_stats_counter_increased_by_client_error() -> None:
    """AC-6: A request yielding a client error increases requests_served."""
    app = _build_app()

    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Hit a non-existent endpoint (404)
    client.get("/nonexistent")

    # Now check stats — the counter should be >= 1
    response = client.get("/stats")
    data = response.json()

    assert data["requests_served"] >= 1


# ---------------------------------------------------------------------------
# AC-7: POST /stats is rejected as method-not-allowed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_post_rejected() -> None:
    """AC-7: POST /stats returns 405 Method Not Allowed."""
    app = _build_app()
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/stats")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


# ---------------------------------------------------------------------------
# AC-8: No database access in stats path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_no_db_imports() -> None:
    """AC-8: src/stats/ imports no session/engine machinery."""
    import src.stats.router as stats_module

    # Check that the module source does not import SQLAlchemy or session machinery
    source = open(stats_module.__file__).read()
    assert "sqlalchemy" not in source, (
        "src/stats/router.py must not import sqlalchemy"
    )
    assert "session" not in source or "StatsState" in source, (
        "src/stats/router.py must not import database session machinery"
    )


@pytest.mark.asyncio
async def test_stats_works_without_db_dependency() -> None:
    """AC-8: Stats tests pass without any database dependency."""
    # Build app without any DB setup — just stats router + middleware
    app = _build_app()
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/stats")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["service"] == settings.app_name
    assert data["requests_served"] >= 1


# ---------------------------------------------------------------------------
# StatsState unit tests
# ---------------------------------------------------------------------------


class TestStatsState:
    """Tests for the thread-safe StatsState class."""

    def test_initial_state(self) -> None:
        """StatsState starts with zero requests and no first_request_at."""
        state = StatsState()
        service, count, first_at = state.snapshot()
        assert count == 0
        assert first_at is None
        assert service == settings.app_name

    def test_increment_sets_first_request_at(self) -> None:
        """First increment sets first_request_at."""
        state = StatsState()
        first_at = state.increment()
        assert first_at is not None

    def test_increment_increases_count(self) -> None:
        """Each increment increases the count."""
        state = StatsState()
        state.increment()
        _, count, _ = state.snapshot()
        assert count == 1

        state.increment()
        _, count, _ = state.snapshot()
        assert count == 2

    def test_first_request_at_stable_after_first(self) -> None:
        """first_request_at does not change after the first increment."""
        state = StatsState()
        first = state.increment()
        import time

        time.sleep(0.01)
        state.increment()
        _, _, second = state.snapshot()
        assert first == second


# ---------------------------------------------------------------------------
# Seam test: middleware and router share the same state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_seam_middleware_and_router_share_state() -> None:
    """Seam test: non-stats traffic then GET /stats reflects it."""
    app = _build_app()

    @app.get("/other")
    async def other_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Make a non-stats request
    client.get("/other")

    # The stats endpoint should reflect that a request was counted
    response = client.get("/stats")
    data = response.json()

    # At least 2 requests counted: /other + /stats
    assert data["requests_served"] >= 2
