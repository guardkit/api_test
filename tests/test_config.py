"""Tests for core configuration module."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.core.config import settings


class TestSettings:
    """Tests for the Settings class."""

    def test_settings_has_log_level_field(self) -> None:
        """Settings class has log_level field."""
        assert hasattr(settings, "log_level")

    def test_settings_has_log_format_field(self) -> None:
        """Settings class has log_format field."""
        assert hasattr(settings, "log_format")

    def test_log_level_default_value(self) -> None:
        """log_level has default value of 'INFO'."""
        assert settings.log_level == "INFO"

    def test_log_format_default_value(self) -> None:
        """log_format has default value of 'json'."""
        assert settings.log_format == "json"

    def test_log_level_env_override(self) -> None:
        """log_level is configurable via LOG_LEVEL environment variable."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            from src.core.config import Settings

            new_settings = Settings()
            assert new_settings.log_level == "DEBUG"

    def test_log_format_env_override(self) -> None:
        """log_format is configurable via LOG_FORMAT environment variable."""
        with patch.dict(os.environ, {"LOG_FORMAT": "console"}):
            from src.core.config import Settings

            new_settings = Settings()
            assert new_settings.log_format == "console"

    def test_log_level_various_values(self) -> None:
        """log_level accepts various valid values."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            with patch.dict(os.environ, {"LOG_LEVEL": level}):
                from src.core.config import Settings

                new_settings = Settings()
                assert new_settings.log_level == level

    def test_log_format_various_values(self) -> None:
        """log_format accepts various valid values."""
        valid_formats = ["json", "console"]
        for fmt in valid_formats:
            with patch.dict(os.environ, {"LOG_FORMAT": fmt}):
                from src.core.config import Settings

                new_settings = Settings()
                assert new_settings.log_format == fmt
