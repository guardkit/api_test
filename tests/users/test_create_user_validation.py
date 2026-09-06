"""Tests for user creation endpoint validation.

These tests verify the POST /users endpoint properly rejects requests
with missing or invalid required fields.
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient


class TestCreateUserMissingFields:
    """Tests for rejecting user creation with missing required fields."""

    @pytest.mark.asyncio
    async def test_create_user_missing_email_returns_422(
        self, async_client: AsyncClient
    ) -> None:
        """Endpoint rejects user creation when email is missing.

        The email field is required for user creation. A POST request
        without an email body should return 422 Unprocessable Entity.
        """
        payload = {"full_name": "No Email User"}

        response = await async_client.post("/users", json=payload)

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data
        errors = data["detail"]
        assert isinstance(errors, list)
        error_fields = [e["loc"][-1] for e in errors]
        assert "email" in error_fields

    @pytest.mark.asyncio
    async def test_create_user_missing_body_returns_422(
        self, async_client: AsyncClient
    ) -> None:
        """Endpoint rejects user creation when request body is empty.

        A POST request with no JSON body should return 422 Unprocessable Entity.
        """
        response = await async_client.post("/users", json={})

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_create_user_invalid_email_returns_422(
        self, async_client: AsyncClient
    ) -> None:
        """Endpoint rejects user creation when email is malformed.

        The email field must be a valid email address. An invalid email
        should return 422 Unprocessable Entity.
        """
        payload = {"email": "not-an-email"}

        response = await async_client.post("/users", json=payload)

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data
