"""Tests for health check schemas."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.health.router import router
from src.health.schemas import HealthResponse


@pytest.fixture
def test_app() -> FastAPI:
    """Create a test FastAPI app with the health router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """Create a test client for the app."""
    return TestClient(test_app)


class TestHealthResponseSchema:
    """Tests for HealthResponse schema examples and field descriptions."""

    def test_health_response_has_json_schema_extra(self) -> None:
        """Test that HealthResponse includes json_schema_extra with examples."""
        examples = HealthResponse.model_config["json_schema_extra"]["examples"]

        assert isinstance(examples, list)
        assert len(examples) >= 1
        assert examples[0] == {"status": "ok", "version": "0.1.0", "log_level": "INFO", "log_format": "json"}

    def test_health_response_has_logging_fields(self) -> None:
        """Test that HealthResponse includes log_level and log_format fields."""
        schema = HealthResponse.model_json_schema()

        # Check log_level field exists with description
        assert "log_level" in schema["properties"]
        assert "description" in schema["properties"]["log_level"]
        assert schema["properties"]["log_level"]["description"] == "Current configured log level (e.g., INFO, DEBUG)"

        # Check log_format field exists with description
        assert "log_format" in schema["properties"]
        assert "description" in schema["properties"]["log_format"]
        assert schema["properties"]["log_format"]["description"] == "Current configured log format (e.g., json, console)"

    def test_health_response_has_field_descriptions(self) -> None:
        """Test that HealthResponse fields have descriptions via Field()."""
        schema = HealthResponse.model_json_schema()

        # Check status field description
        assert "status" in schema["properties"]
        assert "description" in schema["properties"]["status"]
        assert schema["properties"]["status"]["description"] == "Service health status"

        # Check version field description
        assert "version" in schema["properties"]
        assert "description" in schema["properties"]["version"]
        assert schema["properties"]["version"]["description"] == "API version string"

    def test_openapi_schema_contains_examples(self, client: TestClient) -> None:
        """Test that OpenAPI schema shows examples in HealthResponse component."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        openapi_schema = response.json()
        components = openapi_schema.get("components", {})
        schemas = components.get("schemas", {})

        assert "HealthResponse" in schemas
        health_response_schema = schemas["HealthResponse"]

        assert "examples" in health_response_schema
        assert health_response_schema["examples"] == [
            {"status": "ok", "version": "0.1.0", "log_level": "INFO", "log_format": "json"}
        ]

    def test_openapi_schema_includes_logging_fields(self, client: TestClient) -> None:
        """Test that OpenAPI schema includes log_level and log_format fields."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        openapi_schema = response.json()
        components = openapi_schema.get("components", {})
        schemas = components.get("schemas", {})

        assert "HealthResponse" in schemas
        health_response_schema = schemas["HealthResponse"]
        properties = health_response_schema.get("properties", {})

        # Verify log_level field is present
        assert "log_level" in properties
        assert properties["log_level"]["type"] == "string"
        assert properties["log_level"]["description"] == "Current configured log level (e.g., INFO, DEBUG)"

        # Verify log_format field is present
        assert "log_format" in properties
        assert properties["log_format"]["type"] == "string"
        assert properties["log_format"]["description"] == "Current configured log format (e.g., json, console)"

    def test_openapi_path_contains_response_descriptions(self, client: TestClient) -> None:
        """Test that OpenAPI paths contain response descriptions."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        openapi_schema = response.json()
        paths = openapi_schema.get("paths", {})

        assert "/health" in paths
        health_path = paths["/health"]
        get_operation = health_path.get("get", {})

        assert "responses" in get_operation
        assert "200" in get_operation["responses"]
        assert get_operation["responses"]["200"]["description"] == "Service is healthy"


class TestBaseSchema:
    """Tests for the shared BaseSchema class."""

    def test_base_schema_is_inheritable(self) -> None:
        """Test that BaseSchema can be inherited."""
        from src.schemas import BaseSchema

        class TestSchema(BaseSchema):
            name: str

        instance = TestSchema(name="test")
        assert instance.name == "test"
