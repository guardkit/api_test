"""Tests for error scenarios in the user count endpoints."""

from __future__ import annotations

from http import HTTPStatus
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from src.users import crud


class TestUserCountDatabaseErrors:
    """Tests for database error scenarios in the /users/count endpoint."""

    @pytest.mark.asyncio
    async def test_count_returns_503_when_db_unavailable(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that GET /users/count returns 503 when database is unavailable.

        Verifies that SQLAlchemyError raised during count_users is
        translated to HTTP 503 Service Unavailable with an appropriate
        error detail message.
        """
        with patch.object(crud, "count_users") as mock_count:
            mock_count.side_effect = SQLAlchemyError("Database connection failed")

            response = await async_client.get("/users/count")

            assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
            data = response.json()
            assert "Database unavailable" in data["detail"]

    @pytest.mark.asyncio
    async def test_count_today_returns_503_when_db_unavailable(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that GET /users/count-today returns 503 when database is unavailable.

        Verifies that SQLAlchemyError raised during count_users_today is
        translated to HTTP 503 Service Unavailable with an appropriate
        error detail message.
        """
        with patch.object(crud, "count_users_today") as mock_count:
            mock_count.side_effect = SQLAlchemyError("Database connection failed")

            response = await async_client.get("/users/count-today")

            assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
            data = response.json()
            assert "Database unavailable" in data["detail"]


class TestUserCountInvalidRequestFormat:
    """Tests for invalid request format scenarios in the user count endpoints.

    Note: FastAPI returns 405 Method Not Allowed when sending POST to a
    GET-only route. PUT and DELETE to /users/count are routed to the
    /{user_id} route instead, so they are not tested here.
    """

    @pytest.mark.asyncio
    async def test_count_rejects_post_with_invalid_method(
        self, async_client: AsyncClient
    ) -> None:
        """Test that POST to /users/count returns 405 Method Not Allowed.

        Verifies that the count endpoint only accepts GET requests and
        rejects other HTTP methods with an appropriate status code.
        """
        response = await async_client.post("/users/count")

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    @pytest.mark.asyncio
    async def test_count_today_rejects_post_with_invalid_method(
        self, async_client: AsyncClient
    ) -> None:
        """Test that POST to /users/count-today returns 405 Method Not Allowed.

        Verifies that the count-today endpoint only accepts GET requests
        and rejects other HTTP methods with an appropriate status code.
        """
        response = await async_client.post("/users/count-today")

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
