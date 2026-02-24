"""Tests for API versioning middleware."""

from __future__ import annotations

from src.core.config import settings
from src.core.middleware import APIVersionHeaderMiddleware
from src.main import app


class TestAPIVersionHeaderMiddleware:
    """Tests for the APIVersionHeaderMiddleware class."""

    def test_middleware_can_be_instantiated(self) -> None:
        """Test that APIVersionHeaderMiddleware can be instantiated."""
        middleware = APIVersionHeaderMiddleware(app)
        assert isinstance(middleware, APIVersionHeaderMiddleware)

    def test_middleware_has_dispatch_method(self) -> None:
        """Test that middleware has dispatch method."""
        middleware = APIVersionHeaderMiddleware(app)
        assert hasattr(middleware, "dispatch")
        assert callable(middleware.dispatch)


class TestVersionHeaderOnResponses:
    """Tests that X-API-Version header is present on various responses."""

    def test_health_endpoint_includes_version_header(self, client) -> None:
        """Test that GET /health response includes X-API-Version header."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "X-API-Version" in response.headers
        assert response.headers["X-API-Version"] == settings.app_version

    def test_openapi_includes_version_header(self, client) -> None:
        """Test that GET /openapi.json response includes X-API-Version header."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "X-API-Version" in response.headers
        assert response.headers["X-API-Version"] == settings.app_version

    def test_version_header_matches_settings(self, client) -> None:
        """Test that X-API-Version header value matches settings.app_version."""
        response = client.get("/health")
        assert response.headers["X-API-Version"] == settings.app_version
