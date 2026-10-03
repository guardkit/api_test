"""Tests for the ``GET /users/active-count`` endpoint (FEAT-651C).

The route is exercised through the application, with the real database behind
the ``override_get_db`` override, so what is asserted is the HTTP contract:
status, body shape, and which methods the path answers.

The query underneath is pinned by ``test_active_count_crud.py`` (TASK-651C-002)
and the response schema itself by ``test_schemas.py`` (TASK-651C-001). The
end-to-end scenario set for this feature belongs to TASK-651C-004, in
``tests/users/test_active_count.py``; nothing here freezes that boundary.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import ActiveCountResponse, UserCreate, UserUpdate

WRITE_METHODS = ("post", "put", "patch", "delete")


async def _make_user(db_session: AsyncSession, email: str, *, is_active: bool) -> str:
    """Create a live user through the application's own CRUD layer."""
    user = await crud.create_user(db_session, UserCreate(email=email))
    updated = await crud.update_user(
        db_session, user.id, UserUpdate(is_active=is_active)
    )
    assert updated is not None
    return updated.id


def _response_schema(openapi: dict[str, Any], path: str) -> dict[str, Any]:
    """Return the 200 response schema of a path, resolving a ``$ref`` if used."""
    schema: dict[str, Any] = openapi["paths"][path]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    ref = schema.get("$ref")
    if isinstance(ref, str):
        return openapi["components"]["schemas"][ref.rsplit("/", 1)[-1]]
    return schema


class TestActiveCountEndpointContract:
    """AC-001/AC-002: GET answers 200 with both counts, in the schema's shape."""

    async def test_returns_both_counts(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-001: 200 OK carrying the active and the inactive count."""
        await _make_user(db_session, "on-1@example.com", is_active=True)
        await _make_user(db_session, "on-2@example.com", is_active=True)
        await _make_user(db_session, "off-1@example.com", is_active=False)

        response = await async_client.get("/users/active-count")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"active_count": 2, "inactive_count": 1}

    async def test_empty_database_yields_zero_for_both(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-001: with nothing to count, both counts are present and 0."""
        response = await async_client.get("/users/active-count")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"active_count": 0, "inactive_count": 0}

    async def test_body_is_exactly_the_response_schema(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-002: the wire body is ActiveCountResponse — no extra, no missing."""
        await _make_user(db_session, "someone@example.com", is_active=True)

        body = (await async_client.get("/users/active-count")).json()

        assert set(body) == set(ActiveCountResponse.model_fields)
        assert ActiveCountResponse.model_validate(body).model_dump() == body
        assert all(isinstance(value, int) for value in body.values())

    async def test_documented_response_matches_the_schema(
        self, async_client: AsyncClient
    ) -> None:
        """AC-002: the published contract names the same two integer counts."""
        openapi = (await async_client.get("/openapi.json")).json()

        properties = _response_schema(openapi, "/users/active-count")["properties"]

        assert set(properties) == set(ActiveCountResponse.model_fields)
        assert all(field["type"] == "integer" for field in properties.values()), (
            "both counts must be published as integers"
        )

    async def test_counts_follow_the_current_state(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-001: each request reports the state as it is at that moment."""
        first = await _make_user(db_session, "before@example.com", is_active=True)
        assert (await async_client.get("/users/active-count")).json() == {
            "active_count": 1,
            "inactive_count": 0,
        }

        await crud.update_user(db_session, first, UserUpdate(is_active=False))
        await _make_user(db_session, "after@example.com", is_active=False)

        assert (await async_client.get("/users/active-count")).json() == {
            "active_count": 0,
            "inactive_count": 2,
        }

    async def test_counts_add_up_to_the_total_count(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """The split is of the same population /users/count totals."""
        await _make_user(db_session, "a@example.com", is_active=True)
        await _make_user(db_session, "b@example.com", is_active=False)
        deleted = await _make_user(db_session, "c@example.com", is_active=True)
        assert await crud.delete_user(db_session, deleted) is True

        counts = (await async_client.get("/users/active-count")).json()
        total = (await async_client.get("/users/count")).json()

        assert counts["active_count"] + counts["inactive_count"] == total["count"]
        assert counts == {"active_count": 1, "inactive_count": 1}

    async def test_returns_503_when_the_database_fails(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """A query failure is translated at the boundary, as in /users/count."""
        with patch.object(
            crud, "get_active_user_counts", side_effect=SQLAlchemyError("down")
        ):
            response = await async_client.get("/users/active-count")

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert "Database unavailable" in response.json()["detail"]


class TestActiveCountEndpointIsReadOnly:
    """AC-003: the path answers reads only."""

    @pytest.mark.parametrize("method", WRITE_METHODS)
    async def test_write_methods_are_refused(
        self, async_client: AsyncClient, override_get_db: None, method: str
    ) -> None:
        """AC-003: POST/PUT/PATCH/DELETE get 405 (or 404), never a write."""
        response = await async_client.request(
            method.upper(),
            "/users/active-count",
            json={"email": "attacker@example.com"},
        )

        assert response.status_code in (
            HTTPStatus.METHOD_NOT_ALLOWED,
            HTTPStatus.NOT_FOUND,
        )

    @pytest.mark.parametrize("method", WRITE_METHODS)
    async def test_write_methods_leave_the_data_alone(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
        method: str,
    ) -> None:
        """AC-003: a refused write really creates nothing."""
        await _make_user(db_session, "kept@example.com", is_active=True)

        await async_client.request(
            method.upper(),
            "/users/active-count",
            json={"email": "attacker@example.com"},
        )

        assert (await async_client.get("/users/active-count")).json() == {
            "active_count": 1,
            "inactive_count": 0,
        }

    async def test_get_still_answers_after_a_refused_write(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-003: refusing the write does not take the read path with it."""
        await async_client.post("/users/active-count", json={})

        assert (
            await async_client.get("/users/active-count")
        ).status_code == HTTPStatus.OK
