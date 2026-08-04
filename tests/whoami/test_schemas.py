"""Tests for whoami schemas."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.whoami.router import router
from src.whoami.schemas import WhoamiResponse


@pytest.fixture
def test_app() -> FastAPI:
    """Create a test FastAPI app with the whoami router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """Create a test client for the app."""
    return TestClient(test_app)


class TestWhoamiResponseSchema:
    """Tests for WhoamiResponse schema examples and field descriptions."""

    def test_whoami_response_has_json_schema_extra(self) -> None:
        """Test that WhoamiResponse includes json_schema_extra with examples."""
        examples = WhoamiResponse.model_config["json_schema_extra"]["examples"]

        assert isinstance(examples, list)
        assert len(examples) >= 1
        assert examples[0] == {"service": "api_test"}

    def test_whoami_response_has_service_field(self) -> None:
        """Test that WhoamiResponse includes a service field with description."""
        schema = WhoamiResponse.model_json_schema()

        assert "service" in schema["properties"]
        assert "description" in schema["properties"]["service"]
        assert schema["properties"]["service"]["description"] == (
            "The name of the API service"
        )

    def test_whoami_response_validates_correctly(self) -> None:
        """Test that WhoamiResponse validates a correct payload."""
        response = WhoamiResponse(service="api_test")
        assert response.service == "api_test"

    def test_openapi_schema_contains_examples(self, client: TestClient) -> None:
        """Test that OpenAPI schema shows examples in WhoamiResponse component."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        openapi_schema = response.json()
        components = openapi_schema.get("components", {})
        schemas = components.get("schemas", {})

        assert "WhoamiResponse" in schemas
        whoami_response_schema = schemas["WhoamiResponse"]

        assert "examples" in whoami_response_schema
        assert whoami_response_schema["examples"] == [{"service": "api_test"}]

    def test_openapi_schema_includes_service_field(self, client: TestClient) -> None:
        """Test that OpenAPI schema includes service field."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        openapi_schema = response.json()
        components = openapi_schema.get("components", {})
        schemas = components.get("schemas", {})

        assert "WhoamiResponse" in schemas
        whoami_response_schema = schemas["WhoamiResponse"]
        properties = whoami_response_schema.get("properties", {})

        assert "service" in properties
        assert properties["service"]["type"] == "string"
        assert properties["service"]["description"] == "The name of the API service"
