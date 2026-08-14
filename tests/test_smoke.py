"""Smoke tests for critical API endpoints.

Smoke tests are fast, basic sanity checks that verify core functionality.
These tests are designed to catch obvious failures early in the test suite
and can be run frequently in CI/CD pipelines.
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ready_endpoint_returns_200_ok(async_client: AsyncClient) -> None:
    """Smoke test: Verify GET /ready returns 200 OK.

    This is a critical smoke test that verifies the readiness endpoint
    is accessible and responds successfully. This endpoint is typically
    used by Kubernetes readiness probes and load balancers.

    This is an invariant test: the /ready endpoint must always return
    200 OK when the service is running, regardless of other features
    or configuration changes.
    """
    response = await async_client.get("/ready")

    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_ready_endpoint_post_returns_405_method_not_allowed(
    async_client: AsyncClient,
) -> None:
    """Smoke test: Verify POST /ready returns 405 Method Not Allowed.

    This smoke test verifies that the /ready endpoint correctly rejects
    POST requests with HTTP 405 Method Not Allowed. The /ready endpoint
    should only accept GET requests.

    This is an invariant test: the /ready endpoint must never accept
    POST requests, as it is a read-only status check endpoint.
    """
    response = await async_client.post("/ready")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
