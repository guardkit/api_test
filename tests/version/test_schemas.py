"""Tests for version schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.version.schemas import VersionResponse


def test_version_response_schema_valid() -> None:
    """Test that VersionResponse accepts valid data."""
    data = {
        "version": "0.1.0",
        "commit": "abc1234",
        "service": "api",
    }

    response = VersionResponse(**data)

    assert response.version == "0.1.0"
    assert response.commit == "abc1234"
    assert response.service == "api"


def test_version_response_schema_requires_version() -> None:
    """Test that VersionResponse requires version field."""
    data = {
        "commit": "abc1234",
        "service": "api",
    }

    with pytest.raises(ValidationError) as exc_info:
        VersionResponse(**data)

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("version",) for error in errors)


def test_version_response_schema_requires_commit() -> None:
    """Test that VersionResponse requires commit field."""
    data = {
        "version": "0.1.0",
        "service": "api",
    }

    with pytest.raises(ValidationError) as exc_info:
        VersionResponse(**data)

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("commit",) for error in errors)


def test_version_response_schema_requires_service() -> None:
    """Test that VersionResponse requires service field."""
    data = {
        "version": "0.1.0",
        "commit": "abc1234",
    }

    with pytest.raises(ValidationError) as exc_info:
        VersionResponse(**data)

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("service",) for error in errors)


def test_version_response_schema_json_serialization() -> None:
    """Test that VersionResponse serializes to JSON correctly."""
    response = VersionResponse(
        version="0.1.0",
        commit="abc1234",
        service="api",
    )

    json_data = response.model_dump()

    assert json_data == {
        "version": "0.1.0",
        "commit": "abc1234",
        "service": "api",
    }


def test_version_response_schema_accepts_unknown_commit() -> None:
    """Test that VersionResponse accepts 'unknown' as commit value."""
    response = VersionResponse(
        version="0.1.0",
        commit="unknown",
        service="api",
    )

    assert response.commit == "unknown"


def test_version_response_schema_fields_are_strings() -> None:
    """Test that all VersionResponse fields are strings."""
    response = VersionResponse(
        version="0.1.0",
        commit="abc1234",
        service="api",
    )

    assert isinstance(response.version, str)
    assert isinstance(response.commit, str)
    assert isinstance(response.service, str)
