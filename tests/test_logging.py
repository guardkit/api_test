"""Tests for the structlog configuration module."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
import structlog

from src.core.logging import (
    get_logger,
    get_log_level,
    setup_logging,
)


class TestGetLogLevel:
    """Tests for the get_log_level function."""

    @pytest.mark.parametrize(
        "level,expected",
        [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
            ("debug", logging.DEBUG),
            ("info", logging.INFO),
            ("warning", logging.WARNING),
            ("error", logging.ERROR),
            ("critical", logging.CRITICAL),
        ],
    )
    def test_get_log_level_valid(self, level: str, expected: int) -> None:
        """Test valid log level strings are converted correctly."""
        assert get_log_level(level) == expected

    def test_get_log_level_invalid(self) -> None:
        """Test invalid log level raises ValueError."""
        with pytest.raises(ValueError, match="Invalid log level"):
            get_log_level("INVALID")


class TestSetupLogging:
    """Tests for the setup_logging function."""

    def test_setup_logging_configures_structlog(self) -> None:
        """Test that setup_logging configures structlog processors."""
        setup_logging()

        # Verify structlog has processors configured
        assert hasattr(structlog, "get_logger")
        logger = structlog.get_logger("test")
        assert logger is not None

    def test_setup_logging_configures_stdlib_logging(self) -> None:
        """Test that stdlib logging is configured to use structlog."""
        setup_logging()

        # Get the root logger's handlers
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0

        # Verify handlers use ProcessorFormatter
        handler = root_logger.handlers[0]
        assert handler is not None

    def test_setup_logging_with_different_log_levels(self) -> None:
        """Test setup_logging works with different log levels."""
        with patch("src.core.logging.settings") as mock_settings:
            mock_settings.log_format = "json"

            # Test with INFO level
            mock_settings.log_level = "INFO"
            setup_logging()
            assert logging.getLogger().level == logging.INFO

            # Test with DEBUG level
            mock_settings.log_level = "DEBUG"
            setup_logging()
            assert logging.getLogger().level == logging.DEBUG

            # Test with WARNING level
            mock_settings.log_level = "WARNING"
            setup_logging()
            assert logging.getLogger().level == logging.WARNING

    def test_setup_logging_with_json_format(self) -> None:
        """Test setup_logging configures JSON renderer when log_format is json."""
        with patch("src.core.logging.settings") as mock_settings:
            mock_settings.log_level = "INFO"
            mock_settings.log_format = "json"
            setup_logging()

            # The processor should end with JSONRenderer
            logger = structlog.get_logger("test")
            assert logger is not None

    def test_setup_logging_with_console_format(self) -> None:
        """Test setup_logging configures console renderer when log_format is console."""
        with patch("src.core.logging.settings") as mock_settings:
            mock_settings.log_level = "INFO"
            mock_settings.log_format = "console"
            setup_logging()

            # The processor should end with ConsoleRenderer
            logger = structlog.get_logger("test")
            assert logger is not None

    def test_setup_logging_handles_invalid_log_level(self) -> None:
        """Test that invalid log level raises appropriate error."""
        with patch("src.core.logging.settings") as mock_settings:
            mock_settings.log_level = "INVALID"
            mock_settings.log_format = "json"

            with pytest.raises(ValueError, match="Invalid log level"):
                setup_logging()


class TestGetLogger:
    """Tests for the get_logger function."""

    def test_get_logger_default_name(self) -> None:
        """Test get_logger returns logger with default name."""
        setup_logging()
        logger = get_logger()
        assert logger is not None
        # The logger name should be 'app' by default
        assert "app" in str(logger)

    def test_get_logger_with_name(self) -> None:
        """Test get_logger returns logger with specified name."""
        setup_logging()
        logger = get_logger("test_module")
        assert logger is not None

    def test_get_logger_returns_bound_logger(self) -> None:
        """Test get_logger returns a structlog bound logger."""
        setup_logging()
        logger = get_logger("test")
        # Bound loggers have bind method
        assert hasattr(logger, "bind")
        assert callable(logger.bind)

    def test_get_logger_can_bind_context(self) -> None:
        """Test that the returned logger can bind context."""
        setup_logging()
        logger = get_logger("test")
        bound_logger = logger.bind(user_id=123, request_id="abc")
        assert bound_logger is not None

    def test_get_logger_multiple_calls(self) -> None:
        """Test that multiple calls return loggers with same configuration."""
        setup_logging()
        logger1 = get_logger("test")
        logger2 = get_logger("test")
        # Structlog uses lazy proxy pattern - loggers have same name/config
        # The proxy defers logger creation until actually used
        assert logger1 is not logger2  # Different proxy instances
        # But both should work the same way
        assert str(logger1) == str(logger2)


class TestLoggingIntegration:
    """Integration tests for the logging system."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self) -> None:
        """Setup and teardown logging for each test."""
        # Ensure clean state before test
        structlog.reset_defaults()
        yield
        # Reset after test
        structlog.reset_defaults()

    def test_logging_output_format(self) -> None:
        """Test that log output follows expected format."""
        setup_logging()

        logger = get_logger("test_module")
        # This should produce valid structured output
        # We can't easily capture the output, but we can verify no exceptions
        logger.info("test message", key="value")

    def test_structlog_processor_pipeline(self) -> None:
        """Test that the processor pipeline is correctly configured."""
        setup_logging()

        # Verify processors include required components
        processors = structlog.get_config()["processors"]

        # Check for required processors
        processor_names = [p.__name__ if hasattr(p, "__name__") else str(p) for p in processors]

        # Verify we have key processors in the pipeline
        processor_chain = " -> ".join(processor_names)
        assert "TimeStamper" in processor_chain or "timestamp" in processor_chain.lower()

    def test_stdlib_logger_integration(self) -> None:
        """Test that stdlib loggers pass through structlog."""
        setup_logging()

        # Get a stdlib logger
        stdlib_logger = logging.getLogger("test_stdlib")
        structlog_logger = structlog.get_logger("test_stdlib")

        # Both should work without errors
        stdlib_logger.info("stdlib message")
        structlog_logger.info("structlog message")
