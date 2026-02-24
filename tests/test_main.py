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
