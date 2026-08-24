"""Tests for ETag generation logic and middleware."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from src.core.etag import ETagMiddleware, etag_matches, generate_etag


class TestGenerateETag:
    """Tests for ETag generation from resource data."""

    def test_etag_is_strong_validator(self) -> None:
        """Test that the ETag is wrapped in double quotes (strong validator)."""
        data = {"id": "1", "email": "test@example.com", "full_name": "Test User"}
        etag = generate_etag(data)
        assert etag.startswith('"')
        assert etag.endswith('"')

    def test_etag_is_hex_digest(self) -> None:
        """Test that the ETag body is a SHA-256 hex digest (64 hex chars)."""
        data = {"id": "1", "email": "test@example.com", "full_name": "Test User"}
        etag = generate_etag(data)
        # Remove the surrounding quotes
        digest = etag[1:-1]
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_etag_deterministic_for_identical_state(self) -> None:
        """Test that identical resource data produces the same ETag."""
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "john.doe@example.com",
            "full_name": "John Doe",
            "is_active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        etag1 = generate_etag(data)
        etag2 = generate_etag(data)
        assert etag1 == etag2

    def test_etag_different_for_different_state(self) -> None:
        """Test that different resource data produces different ETags."""
        data_a = {"email": "alice@example.com", "full_name": "Alice"}
        data_b = {"email": "bob@example.com", "full_name": "Bob"}
        etag_a = generate_etag(data_a)
        etag_b = generate_etag(data_b)
        assert etag_a != etag_b

    def test_etag_based_on_hash_of_resource_body(self) -> None:
        """Test that ETag is derived from a hash of the resource body."""
        data = {"id": "1", "email": "test@example.com"}
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        import hashlib

        expected_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        etag = generate_etag(data)
        expected_etag = f'"{expected_digest}"'
        assert etag == expected_etag

    def test_etag_handles_nested_dict(self) -> None:
        """Test ETag generation with nested dictionary data."""
        data = {
            "id": "1",
            "profile": {"name": "Test", "age": 30},
            "tags": ["admin", "user"],
        }
        etag = generate_etag(data)
        assert etag.startswith('"')
        assert etag.endswith('"')
        # Deterministic
        assert generate_etag(data) == generate_etag(data)

    def test_etag_handles_primitive_types(self) -> None:
        """Test ETag generation with primitive data types."""
        assert generate_etag("simple string") != generate_etag("different string")
        assert generate_etag(42) != generate_etag(43)
        assert generate_etag(True) != generate_etag(False)
        assert generate_etag(None) != generate_etag([])

    def test_etag_order_independent_for_dict_keys(self) -> None:
        """Test that key order in dict does not affect ETag (canonical JSON)."""
        data_a = {"a": 1, "b": 2, "c": 3}
        data_b = {"c": 3, "b": 2, "a": 1}
        assert generate_etag(data_a) == generate_etag(data_b)


class TestETagMatches:
    """Tests for ETag comparison logic."""

    def test_etag_matches_when_identical(self) -> None:
        """Test that etag_matches returns True when ETags are identical."""
        data = {"id": "1", "email": "test@example.com"}
        etag = generate_etag(data)
        assert etag_matches(etag, data) is True

    def test_etag_no_match_when_data_changed(self) -> None:
        """Test that etag_matches returns False when data has changed."""
        data_a = {"id": "1", "email": "test@example.com"}
        data_b = {"id": "1", "email": "changed@example.com"}
        etag = generate_etag(data_a)
        assert etag_matches(etag, data_b) is False

    def test_etag_no_match_when_none(self) -> None:
        """Test that etag_matches returns False when no ETag is provided."""
        data = {"id": "1", "email": "test@example.com"}
        assert etag_matches(None, data) is False

    def test_etag_no_match_when_different_data(self) -> None:
        """Test that etag_matches returns False for different resource state."""
        data_a = {"name": "Alice", "age": 30}
        data_b = {"name": "Bob", "age": 25}
        etag = generate_etag(data_a)
        assert etag_matches(etag, data_b) is False


class TestETagMiddleware:
    """Tests for the ETagMiddleware class."""

    @pytest.fixture
    def etag_app(self) -> FastAPI:
        """Create a FastAPI app with ETagMiddleware for testing."""
        app = FastAPI()

        @app.get("/resource")
        def get_resource() -> JSONResponse:
            return JSONResponse(content={"id": "1", "email": "test@example.com"})

        @app.post("/resource")
        def create_resource() -> JSONResponse:
            return JSONResponse(
                status_code=201,
                content={"id": "2", "email": "new@example.com"},
            )

        app.add_middleware(ETagMiddleware)
        return app

    @pytest.fixture
    def client(self, etag_app: FastAPI) -> TestClient:
        """Create a TestClient for the ETag app."""
        return TestClient(etag_app)

    def test_middleware_can_be_instantiated(self) -> None:
        """Test that ETagMiddleware can be instantiated."""
        app = FastAPI()
        middleware = ETagMiddleware(app)
        assert isinstance(middleware, ETagMiddleware)

    def test_middleware_has_call_method(self) -> None:
        """Test that middleware has callable __call__ method."""
        app = FastAPI()
        middleware = ETagMiddleware(app)
        assert hasattr(middleware, "__call__")
        assert callable(middleware.__call__)

    def test_get_without_if_none_match_returns_200(self, client: TestClient) -> None:
        """Test that GET without If-None-Match returns 200 OK."""
        response = client.get("/resource")
        assert response.status_code == 200
        assert "ETag" in response.headers

    def test_get_with_matching_if_none_match_returns_304(
        self, client: TestClient
    ) -> None:
        """Test that GET with matching If-None-Match returns 304 Not Modified."""
        # First, get the ETag
        response = client.get("/resource")
        assert response.status_code == 200
        etag = response.headers["ETag"]

        # Now send the same ETag in If-None-Match
        response = client.get("/resource", headers={"If-None-Match": etag})
        assert response.status_code == 304
        assert response.headers["ETag"] == etag

    def test_get_with_non_matching_if_none_match_returns_200(
        self, client: TestClient
    ) -> None:
        """Test that GET with non-matching If-None-Match returns 200 OK."""
        response = client.get(
            "/resource", headers={"If-None-Match": '"different-etag"'}
        )
        assert response.status_code == 200
        assert "ETag" in response.headers
        data = response.json()
        assert data["id"] == "1"

    def test_post_not_affected_by_etag_middleware(self, client: TestClient) -> None:
        """Test that POST requests bypass ETag validation."""
        response = client.post(
            "/resource",
            headers={"If-None-Match": '"some-etag"'},
        )
        assert response.status_code == 201

    def test_middleware_handles_wildcard_if_none_match(
        self, client: TestClient
    ) -> None:
        """Test that If-None-Match: * returns 304 when resource exists."""
        # First get the ETag
        response = client.get("/resource")
        assert response.status_code == 200

        # Wildcard should match any existing entity
        response = client.get("/resource", headers={"If-None-Match": "*"})
        assert response.status_code == 304

    def test_middleware_handles_multiple_etags_in_if_none_match(
        self, client: TestClient
    ) -> None:
        """Test If-None-Match with multiple ETags returns 304 if any match."""
        response = client.get("/resource")
        etag = response.headers["ETag"]

        # Send multiple ETags including the matching one
        response = client.get(
            "/resource",
            headers={"If-None-Match": f'"other-etag", {etag}, "another-etag"'},
        )
        assert response.status_code == 304

    def test_middleware_handles_malformed_if_none_match(
        self, client: TestClient
    ) -> None:
        """Test that malformed If-None-Match returns full resource gracefully."""
        response = client.get(
            "/resource",
            headers={"If-None-Match": "not-valid-etag-format"},
        )
        # Should return 200 with full body, not crash
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "1"
