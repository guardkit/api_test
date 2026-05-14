"""Tests for the version router."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_version_endpoint_returns_expected_payload(
    async_client: AsyncClient,
) -> None:
    """GET /version returns a 200 with all four version fields populated."""
    response = await async_client.get("/version")

    assert response.status_code == HTTPStatus.OK

    data = response.json()

    # All four required keys are present
    expected_keys = {"service", "version", "git_sha", "build_time"}
    assert expected_keys.issubset(data.keys())

    # Each value is a non-empty string
    for key in expected_keys:
        assert isinstance(data[key], str)
        assert data[key] != ""

    # Default settings produce these exact values when env vars are unset
    assert data["service"] == "api_test"
    assert data["version"] == "0.1.0"
    assert data["git_sha"] == "unknown"
    assert data["build_time"] == "unknown"
