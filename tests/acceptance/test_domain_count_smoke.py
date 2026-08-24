"""Smoke tests for the GET /users/count-by-domain endpoint.

These are fast, basic sanity checks that verify the domain count endpoint
is accessible and responds correctly. These tests are designed to catch
obvious failures early in the test suite.

Invariant tests: the endpoint contract is that GET /users/count-by-domain
always returns a JSON array of {domain, count} objects, and unsupported
methods are always rejected.
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_smoke_domain_count_endpoint_returns_200(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """Smoke test: Verify GET /users/count-by-domain returns 200 OK.

    This is a critical smoke test that verifies the domain count endpoint
    is accessible and responds successfully. This endpoint returns domain
    counts even with an empty user set.
    """
    response = await async_client.get("/users/count-by-domain")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_smoke_domain_count_response_schema(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """Smoke test: Verify GET /users/count-by-domain returns correct response schema.

    The response must be a JSON array where each element has:
    - domain (string)
    - count (integer)
    """
    response = await async_client.get("/users/count-by-domain")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert isinstance(data, list)

    # Empty set is valid; schema invariant: if entries exist, each has domain+count
    for entry in data:
        assert "domain" in entry
        assert "count" in entry
        assert isinstance(entry["domain"], str)
        assert isinstance(entry["count"], int)
