"""Tests for health check schemas."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.health.router import router
from src.health.schemas import HealthResponse, ReadyResponse


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
        expected = {
            "status": "ok",
            "version": "0.1.0",
            "log_level": "INFO",
            "log_format": "json",
        }
        assert examples[0] == expected

    def test_health_response_has_logging_fields(self) -> None:
        """Test that HealthResponse includes log_level and log_format fields."""
        schema = HealthResponse.model_json_schema()

        # Check log_level field exists with description
        assert "log_level" in schema["properties"]
        assert "description" in schema["properties"]["log_level"]
        expected_log_level_desc = (
            "Current configured log level (e.g., INFO, DEBUG)"
        )
        assert schema["properties"]["log_level"]["description"] == (
            expected_log_level_desc
        )

        # Check log_format field exists with description
        assert "log_format" in schema["properties"]
        assert "description" in schema["properties"]["log_format"]
        expected_log_format_desc = (
            "Current configured log format (e.g., json, console)"
        )
        assert schema["properties"]["log_format"]["description"] == (
            expected_log_format_desc
        )

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
        expected = [
            {
                "status": "ok",
                "version": "0.1.0",
                "log_level": "INFO",
                "log_format": "json",
            }
        ]
        assert health_response_schema["examples"] == expected

    def test_openapi_schema_includes_logging_fields(
        self, client: TestClient
    ) -> None:
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
        expected_log_level_desc = (
            "Current configured log level (e.g., INFO, DEBUG)"
        )
        assert properties["log_level"]["description"] == expected_log_level_desc

        # Verify log_format field is present
        assert "log_format" in properties
        assert properties["log_format"]["type"] == "string"
        expected_log_format_desc = (
            "Current configured log format (e.g., json, console)"
        )
        assert (
            properties["log_format"]["description"] == expected_log_format_desc
        )

    def test_openapi_path_contains_response_descriptions(
        self, client: TestClient
    ) -> None:
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


class TestReadyResponseSchema:
    """Tests for ReadyResponse schema examples and field descriptions."""

    def test_ready_response_has_json_schema_extra(self) -> None:
        """Test that ReadyResponse includes json_schema_extra with examples."""
        examples = ReadyResponse.model_config["json_schema_extra"]["examples"]

        assert isinstance(examples, list)
        assert len(examples) >= 1
        assert "status" in examples[0]
        assert "service" in examples[0]

    def test_ready_response_has_required_fields(self) -> None:
        """Test that ReadyResponse includes status and service fields."""
        schema = ReadyResponse.model_json_schema()

        # Check status field exists with description
        assert "status" in schema["properties"]
        assert "description" in schema["properties"]["status"]
        assert (
            schema["properties"]["status"]["description"]
            == "Service readiness status"
        )

        # Check service field exists with description
        assert "service" in schema["properties"]
        assert "description" in schema["properties"]["service"]
        expected_service_desc = "The name of the service"
        assert (
            schema["properties"]["service"]["description"]
            == expected_service_desc
        )

    def test_ready_response_can_be_instantiated(self) -> None:
        """Test that ReadyResponse can be instantiated with required fields."""
        response = ReadyResponse(status="ready", service="api_test")

        assert response.status == "ready"
        assert response.service == "api_test"

    def test_openapi_schema_contains_ready_response(self, client: TestClient) -> None:
        """Test that OpenAPI schema includes ReadyResponse component."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        openapi_schema = response.json()
        components = openapi_schema.get("components", {})
        schemas = components.get("schemas", {})

        assert "ReadyResponse" in schemas
        ready_response_schema = schemas["ReadyResponse"]

        # Verify examples are present
        assert "examples" in ready_response_schema
        examples = ready_response_schema["examples"]
        assert len(examples) >= 1
        assert examples[0] == {"status": "ready", "service": "api"}

    def test_openapi_ready_endpoint_references_schema(self, client: TestClient) -> None:
        """Test that /ready endpoint references ReadyResponse schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        openapi_schema = response.json()
        paths = openapi_schema.get("paths", {})

        assert "/ready" in paths
        ready_path = paths["/ready"]
        get_operation = ready_path.get("get", {})

        # Check response references ReadyResponse schema
        assert "responses" in get_operation
        assert "200" in get_operation["responses"]
        response_200 = get_operation["responses"]["200"]
        assert "content" in response_200
        assert "application/json" in response_200["content"]

        schema_ref = response_200["content"]["application/json"]["schema"]
        assert "$ref" in schema_ref
        assert schema_ref["$ref"] == "#/components/schemas/ReadyResponse"


class TestBaseSchema:
    """Tests for the shared BaseSchema class."""

    def test_base_schema_is_inheritable(self) -> None:
        """Test that BaseSchema can be inherited."""
        from src.schemas import BaseSchema

        class TestSchema(BaseSchema):
            name: str

        instance = TestSchema(name="test")
        assert instance.name == "test"
