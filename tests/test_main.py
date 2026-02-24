"""Tests for FastAPI application initialization."""

from __future__ import annotations

from fastapi import FastAPI

from src.core.config import Settings, settings


class TestSettings:
    """Tests for the Settings class."""

    def test_settings_default_values(self) -> None:
        """Test that Settings has correct default values."""
        assert settings.app_name == "api"
        assert settings.app_env == "development"
        assert settings.debug is False

    def test_settings_model_config(self) -> None:
        """Test that Settings has model_config for env file loading."""
        assert hasattr(Settings, "model_config")
        assert isinstance(Settings.model_config, dict)

    def test_settings_has_app_name_field(self) -> None:
        """Test that Settings has app_name field defined."""
        assert "app_name" in Settings.model_fields
        assert "app_env" in Settings.model_fields
        assert "debug" in Settings.model_fields

    def test_settings_documentation_fields(self) -> None:
        """Test that Settings has documentation-related fields."""
        fields = Settings.model_fields
        assert "app_description" in fields
        assert "app_summary" in fields
        assert "app_contact_name" in fields
        assert "app_contact_email" in fields
        assert "app_contact_url" in fields
        assert "app_license_name" in fields
        assert "app_license_url" in fields
        assert "app_terms_of_service" in fields


class TestApp:
    """Tests for the FastAPI application instance."""

    def test_app_instance(self) -> None:
        """Test that app is a FastAPI instance."""
        from src.main import app

        assert isinstance(app, FastAPI)

    def test_app_title(self) -> None:
        """Test that app title is set from settings."""
        from src.main import app

        assert app.title == settings.app_name

    def test_app_version(self) -> None:
        """Test that app version is set correctly."""
        from src.main import app

        assert app.version == "0.1.0"

    def test_app_debug(self) -> None:
        """Test that app debug is set from settings."""
        from src.main import app

        assert app.debug == settings.debug

    def test_app_routes(self) -> None:
        """Test that app has routes list (basic FastAPI functionality)."""
        from src.main import app

        assert hasattr(app, "routes")
        assert isinstance(app.routes, list)

    def test_app_include_router(self) -> None:
        """Test that app has include_router method (for future router setup)."""
        from src.main import app

        assert hasattr(app, "include_router")
        assert callable(app.include_router)


class TestOpenAPIMetadata:
    """Tests for OpenAPI schema metadata configuration."""

    def test_app_description(self) -> None:
        """Test that app.openapi() schema contains info.description."""
        from src.main import app

        openapi_schema = app.openapi()
        assert "info" in openapi_schema
        assert "description" in openapi_schema["info"]
        assert len(openapi_schema["info"]["description"]) > 0

    def test_app_summary(self) -> None:
        """Test that app.openapi() schema contains info.summary."""
        from src.main import app

        openapi_schema = app.openapi()
        assert "info" in openapi_schema
        assert "summary" in openapi_schema["info"]
        assert len(openapi_schema["info"]["summary"]) > 0

    def test_app_contact(self) -> None:
        """Test that app.openapi() schema contains info.contact."""
        from src.main import app

        openapi_schema = app.openapi()
        assert "info" in openapi_schema
        assert "contact" in openapi_schema["info"]
        contact = openapi_schema["info"]["contact"]
        assert "name" in contact
        assert "email" in contact
        assert "url" in contact

    def test_app_license(self) -> None:
        """Test that app.openapi() schema contains info.license."""
        from src.main import app

        openapi_schema = app.openapi()
        assert "info" in openapi_schema
        assert "license" in openapi_schema["info"]
        license_info = openapi_schema["info"]["license"]
        assert "name" in license_info
        assert "url" in license_info

    def test_openapi_tags(self) -> None:
        """Test that app.openapi() schema contains tags with health description."""
        from src.main import app

        openapi_schema = app.openapi()
        assert "tags" in openapi_schema
        tags = openapi_schema["tags"]
        assert isinstance(tags, list)

        health_tags = [t for t in tags if t.get("name") == "health"]
        assert len(health_tags) >= 1
        assert "description" in health_tags[0]

    def test_swagger_ui_parameters(self) -> None:
        """Test that swagger_ui_parameters are configured on the app."""
        from src.main import app

        # Check that swagger_ui_parameters attribute exists
        assert hasattr(app, "swagger_ui_parameters")
        params = app.swagger_ui_parameters
        assert params is not None
        assert params.get("defaultModelsExpandDepth") == -1
        assert params.get("tryItOutEnabled") is True

    def test_terms_of_service(self) -> None:
        """Test that app.openapi() schema contains termsOfService."""
        from src.main import app

        openapi_schema = app.openapi()
        assert "info" in openapi_schema
        assert "termsOfService" in openapi_schema["info"]
        assert len(openapi_schema["info"]["termsOfService"]) > 0
