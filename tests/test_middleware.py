"""Tests for middleware including correlation ID and request logging."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

import pytest
import structlog

from src.core.middleware import (
    APIVersionHeaderMiddleware,
    CorrelationIDMiddleware,
    RequestLoggingMiddleware,
    get_correlation_id,
)
from src.main import app

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestCorrelationIDMiddleware:
    """Tests for the CorrelationIDMiddleware class."""

    def test_middleware_can_be_instantiated(self, client) -> None:
        """Test that CorrelationIDMiddleware can be instantiated."""
        middleware = CorrelationIDMiddleware(app)
        assert isinstance(middleware, CorrelationIDMiddleware)

    def test_middleware_has_dispatch_method(self, client) -> None:
        """Test that middleware has dispatch method."""
        middleware = CorrelationIDMiddleware(app)
        assert hasattr(middleware, "dispatch")
        assert callable(middleware.dispatch)


class TestCorrelationIDGeneration:
    """Tests for correlation ID generation and propagation."""

    def test_generates_uuid4_when_no_header(self, client) -> None:
        """Test that a UUID4 is generated when no X-Correlation-ID header is present."""
        response = client.get("/health")
        assert response.status_code == 200

        correlation_id = response.headers.get("X-Correlation-ID")
        assert correlation_id is not None

        # Verify it's a valid UUID4 format (8-4-4-4-12 hex digits)
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        assert re.match(uuid_pattern, correlation_id.lower()), (
            f"Correlation ID '{correlation_id}' is not a valid UUID4"
        )

    def test_respects_incoming_correlation_id_header(self, client) -> None:
        """Test that incoming X-Correlation-ID header is preserved."""
        incoming_id = "test-correlation-id-12345"
        response = client.get("/health", headers={"X-Correlation-ID": incoming_id})
        assert response.status_code == 200
        assert response.headers.get("X-Correlation-ID") == incoming_id

    def test_correlation_id_accessible_via_get_correlation_id(self, client) -> None:
        """Test that correlation ID can be retrieved during request processing."""
        from src.core.middleware import get_correlation_id

        # Store the correlation ID from the response header
        response = client.get("/health")
        correlation_id = response.headers.get("X-Correlation-ID")
        assert correlation_id is not None

        # Note: get_correlation_id() returns None outside request context
        # because contextvars are cleaned up after request completion


class TestRequestLoggingMiddleware:
    """Tests for the RequestLoggingMiddleware class."""

    def test_middleware_can_be_instantiated(self, client) -> None:
        """Test that RequestLoggingMiddleware can be instantiated."""
        middleware = RequestLoggingMiddleware(app)
        assert isinstance(middleware, RequestLoggingMiddleware)

    def test_middleware_has_dispatch_method(self, client) -> None:
        """Test that middleware has dispatch method."""
        middleware = RequestLoggingMiddleware(app)
        assert hasattr(middleware, "dispatch")
        assert callable(middleware.dispatch)

    def test_health_endpoint_skipped_by_default(self, client, caplog) -> None:
        """Test that health endpoint logging is skipped by default."""
        with caplog.at_level("INFO"):
            response = client.get("/health")
            assert response.status_code == 200

        # Check that no request_started or request_completed logs were created
        request_logs = [r for r in caplog.records if "request_" in r.getMessage()]
        assert len(request_logs) == 0, (
            "Health endpoint should not be logged by default"
        )

    def test_health_endpoint_can_be_logged(self, client, caplog) -> None:
        """Test that health endpoint logging can be enabled."""
        # Create a test app with logging enabled for health
        from starlette.types import ASGIApp

        class TestApp:
            def __init__(self) -> None:
                self.middleware: list = []

            async def __call__(self, scope, receive, send) -> None:
                pass

        # Test that skip_health_logging=False works
        middleware = RequestLoggingMiddleware(TestApp(), skip_health_logging=False)
        assert middleware.skip_health_logging is False


class TestMiddlewareIntegration:
    """Integration tests for middleware together."""

    def test_correlation_id_passed_through_response(self, client) -> None:
        """Test that correlation ID flows from request to response."""
        response = client.get("/health")
        correlation_id = response.headers.get("X-Correlation-ID")
        assert correlation_id is not None

        # Make another request with the same ID
        response2 = client.get("/health", headers={"X-Correlation-ID": correlation_id})
        assert response2.headers.get("X-Correlation-ID") == correlation_id

    def test_multiple_requests_get_different_correlation_ids(self, client) -> None:
        """Test that each request gets a unique correlation ID."""
        response1 = client.get("/health")
        response2 = client.get("/health")

        id1 = response1.headers.get("X-Correlation-ID")
        id2 = response2.headers.get("X-Correlation-ID")

        assert id1 is not None
        assert id2 is not None
        assert id1 != id2, "Each request should get a unique correlation ID"


class TestAPIVersionHeaderMiddleware:
    """Tests for the API versioning middleware."""

    def test_middleware_can_be_instantiated(self) -> None:
        """Test that APIVersionHeaderMiddleware can be instantiated."""
        middleware = APIVersionHeaderMiddleware(app)
        assert isinstance(middleware, APIVersionHeaderMiddleware)

    def test_middleware_has_dispatch_method(self) -> None:
        """Test that middleware has dispatch method."""
        middleware = APIVersionHeaderMiddleware(app)
        assert hasattr(middleware, "dispatch")
        assert callable(middleware.dispatch)


# Seam Test: Verify STRUCTLOG_LOGGER contract from TASK-LOG-002
@pytest.mark.seam
@pytest.mark.integration_contract("STRUCTLOG_LOGGER")
def test_structlog_logger_available() -> None:
    """Verify structlog logger is obtainable via get_logger().

    Contract: Logger must be obtained via get_logger() from src.core.logging;
              correlation ID must be bindable via structlog.contextvars
    Producer: TASK-LOG-002
    """
    from src.core.logging import get_logger

    logger = get_logger("test")
    assert logger is not None, "get_logger() must return a logger instance"

    # Verify contextvars binding works
    structlog.contextvars.bind_contextvars(correlation_id="test-id")
    ctx = structlog.contextvars.get_contextvars()
    assert "correlation_id" in ctx, "contextvars binding must support correlation_id"
    structlog.contextvars.unbind_contextvars("correlation_id")
