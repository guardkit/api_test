"""Tests for error responses on missing users (ASSUM-002).

Verifies that all user-related endpoints return consistent 404 Not Found
responses with JSON error bodies containing a "not found" message when
the requested user does not exist.
"""

from __future__ import annotations

from http import HTTPStatus
from uuid import uuid4

import pytest
from httpx import AsyncClient


class TestGetUserByIdNotFound:
    """Tests for 404 response on GET /users/{id} for missing users."""

    @pytest.mark.asyncio
    async def test_get_user_not_found_returns_404(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """GET /users/{id} returns 404 with JSON error body for missing user.

        Per ASSUM-002, the 404 error response must include a JSON body
        with an error message field indicating the user was not found.
        """
        fake_id = str(uuid4())

        response = await async_client.get(f"/users/{fake_id}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_user_not_found_message_is_specific(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """GET /users/{id} 404 message identifies the missing user.

        The error message should reference the user ID to help with debugging.
        """
        fake_id = str(uuid4())

        response = await async_client.get(f"/users/{fake_id}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert fake_id in data["detail"]


class TestGetUserSummaryNotFound:
    """Tests for 404 response on GET /users/{id}/summary for missing users."""

    @pytest.mark.asyncio
    async def test_user_summary_not_found_returns_404(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """GET /users/{id}/summary returns 404 for missing user.

        Per ASSUM-002, the 404 error response must include a JSON body
        with an error message field indicating the user was not found.
        """
        fake_id = str(uuid4())

        response = await async_client.get(f"/users/{fake_id}/summary")

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_user_summary_not_found_message_is_specific(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """GET /users/{id}/summary 404 message identifies the missing user."""
        fake_id = str(uuid4())

        response = await async_client.get(f"/users/{fake_id}/summary")

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert fake_id in data["detail"]


class TestGetUserByEmailNotFound:
    """Tests for 404 response on GET /users/by-email for missing users."""

    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found_returns_404(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """GET /users/by-email returns 404 for missing user.

        Per ASSUM-002, the 404 error response must include a JSON body
        with an error message field indicating the user was not found.
        """
        fake_email = "nonexistent@example.com"

        response = await async_client.get(f"/users/by-email?email={fake_email}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found_message_contains_email(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """GET /users/by-email 404 message includes the email searched."""
        fake_email = "missing@example.com"

        response = await async_client.get(f"/users/by-email?email={fake_email}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert fake_email in data["detail"]


class TestErrorResponseBodyFormat:
    """Tests for consistent JSON error response body format."""

    @pytest.mark.asyncio
    async def test_error_response_is_json(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """Error responses return valid JSON bodies."""
        fake_id = str(uuid4())

        response = await async_client.get(f"/users/{fake_id}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        # FastAPI TestClient returns parsed JSON; verify it's a dict
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_error_response_detail_is_string(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """Error response detail field is a human-readable string."""
        fake_id = str(uuid4())

        response = await async_client.get(f"/users/{fake_id}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert isinstance(data["detail"], str)
        assert len(data["detail"]) > 0
