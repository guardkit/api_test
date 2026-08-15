"""Tests for the readiness check endpoint."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.health.router import router as health_router
from src.health import readiness


@pytest.fixture
def app() -> FastAPI:
    """Create a test app with only the health router."""
    local_app = FastAPI()
    local_app.include_router(health_router)
    return local_app


@pytest.fixture
def client(app: FastAPI) -> AsyncGenerator[TestClient, None]:
    """Create a test client for the health app."""
    with TestClient(app) as c:
        yield c


class TestReadinessWhenReady:
    """Tests for readiness when service is ready."""

    def setup_method(self) -> None:
        """Ensure readiness is set to ready before each test."""
        readiness.set_ready()

    def teardown_method(self) -> None:
        """Reset readiness state after each test."""
        readiness.set_ready()

    def test_readiness_returns_200_when_ready(self, client: TestClient) -> None:
        """Test that GET /ready returns HTTP 200 when service is ready."""
        response = client.get("/ready")
        assert response.status_code == 200

    def test_readiness_response_body_when_ready(self, client: TestClient) -> None:
        """Test that GET /ready returns correct body when service is ready."""
        response = client.get("/ready")
        data = response.json()
        assert data["status"] == "ready"
        assert "service" in data

    def test_readiness_content_type(self, client: TestClient) -> None:
        """Test that GET /ready returns application/json content type."""
        response = client.get("/ready")
        assert response.headers["content-type"] == "application/json"


class TestReadinessWhenNotReady:
    """Tests for readiness when service is not ready."""

    def setup_method(self) -> None:
        """Ensure readiness is set to not ready before each test."""
        readiness.set_not_ready()

    def teardown_method(self) -> None:
        """Reset readiness state after each test."""
        readiness.set_ready()

    def test_readiness_returns_503_when_not_ready(self, client: TestClient) -> None:
        """Test that GET /ready returns HTTP 503 when service is not ready."""
        response = client.get("/ready")
        assert response.status_code == 503

    def test_readiness_response_body_when_not_ready(self, client: TestClient) -> None:
        """Test that GET /ready returns correct body when not ready."""
        response = client.get("/ready")
        data = response.json()
        assert data["status"] == "not_ready"


class TestReadinessState:
    """Tests for the readiness state module."""

    def setup_method(self) -> None:
        """Reset state before each test."""
        readiness.set_ready()

    def teardown_method(self) -> None:
        """Reset state after each test."""
        readiness.set_ready()

    def test_is_ready_returns_true_when_ready(self) -> None:
        """Test that is_ready() returns True when service is ready."""
        assert readiness.is_ready() is True

    def test_is_ready_returns_false_when_not_ready(self) -> None:
        """Test that is_ready() returns False when service is not ready."""
        readiness.set_not_ready()
        assert readiness.is_ready() is False

    def test_set_ready_sets_state(self) -> None:
        """Test that set_ready() sets the ready state."""
        readiness.set_not_ready()
        readiness.set_ready()
        assert readiness.is_ready() is True

    def test_set_not_ready_sets_state(self) -> None:
        """Test that set_not_ready() sets the not-ready state."""
        readiness.set_ready()
        readiness.set_not_ready()
        assert readiness.is_ready() is False
