"""Tests for ``PATCH /users/{user_id}/deactivate`` (TASK-2FDE-001, FEAT-2FDE).

The route is exercised through the application, with the real database behind
the ``override_get_db`` override, so what is asserted is the HTTP contract:
the status, the body, and what the next request sees. The published OpenAPI
document is checked too, because "documented in the API docs" is one of the
criteria and the generated document is what the interactive docs are built
from.

The write itself goes through the application's own CRUD layer, so these tests
pin the route's decisions (404 for an unknown or soft-deleted id, 409 for an
already inactive user, 200 with the updated user otherwise) rather than the
query underneath, which belongs to the CRUD layer.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_db as app_get_db
from src.main import app
from src.users import crud
from src.users.schemas import UserCreate, UserUpdate


async def _make_user(
    db_session: AsyncSession, email: str, *, is_active: bool = True
) -> str:
    """Create a live user through the application's own CRUD layer."""
    user = await crud.create_user(db_session, UserCreate(email=email))
    if not is_active:
        updated = await crud.update_user(
            db_session, str(user.id), UserUpdate(is_active=False)
        )
        assert updated is not None
        return str(updated.id)
    return str(user.id)


def _operation(openapi: dict[str, Any]) -> dict[str, Any]:
    """Return the published OpenAPI operation for the deactivate route."""
    return openapi["paths"]["/users/{user_id}/deactivate"]["patch"]


def _resolved_schema(openapi: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve a ``$ref`` in a response schema against the document."""
    ref = schema.get("$ref")
    if isinstance(ref, str):
        return openapi["components"]["schemas"][ref.rsplit("/", 1)[-1]]
    return schema


class TestDeactivateAnActiveUser:
    """AC-001: 200 with the updated user, and the change is the one asked for."""

    async def test_returns_200_with_the_updated_user(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-001: an active user comes back inactive, everything else intact."""
        user_id = await _make_user(db_session, "deactivate-me@example.com")

        response = await async_client.patch(f"/users/{user_id}/deactivate")

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["id"] == user_id
        assert body["email"] == "deactivate-me@example.com"
        assert body["is_active"] is False

    async def test_the_deactivation_survives_to_the_next_request(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-001: the 200 is honest — a later GET reports the same user.

        The session dependency does not commit, so a write that was never
        written down would still read back inside this request and lie here.
        """
        user_id = await _make_user(db_session, "later-look@example.com")

        assert (
            await async_client.patch(f"/users/{user_id}/deactivate")
        ).status_code == HTTPStatus.OK

        follow_up = await async_client.get(f"/users/{user_id}")

        assert follow_up.status_code == HTTPStatus.OK
        assert follow_up.json()["is_active"] is False

    async def test_body_is_the_user_response_shape(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-001: the body is the updated user, not a status message."""
        await _make_user(db_session, "shape@example.com", is_active=False)
        user_id = await _make_user(db_session, "shape-active@example.com")

        body = (await async_client.patch(f"/users/{user_id}/deactivate")).json()

        assert {"id", "email", "is_active"} <= set(body)
        assert isinstance(body["created_at"], str)


class TestDeactivateUnknownUser:
    """AC-002: 404 when there is no user to deactivate."""

    async def test_unknown_id_returns_404(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-002: a validly formatted id nobody has says not found."""
        response = await async_client.patch(f"/users/{uuid4()}/deactivate")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "detail" in response.json()

    async def test_soft_deleted_user_returns_404(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-002: a soft-deleted user is not a user this route can act on."""
        user_id = await _make_user(db_session, "already-gone@example.com")
        assert await crud.delete_user(db_session, user_id) is True

        response = await async_client.patch(f"/users/{user_id}/deactivate")

        assert response.status_code == HTTPStatus.NOT_FOUND

    async def test_malformed_id_returns_400(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The id is validated the way every other /users/{user_id} route does."""
        response = await async_client.patch("/users/not-a-uuid/deactivate")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert "detail" in response.json()


class TestDeactivateAlreadyInactiveUser:
    """AC-003: 409 when the user is already inactive."""

    async def test_inactive_user_returns_409(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-003: a second deactivation conflicts rather than repeating."""
        user_id = await _make_user(
            db_session, "already-off@example.com", is_active=False
        )

        response = await async_client.patch(f"/users/{user_id}/deactivate")

        assert response.status_code == HTTPStatus.CONFLICT
        assert "detail" in response.json()

    async def test_conflict_reports_the_user_it_was_asked_about(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-003: the conflict names the user, so the caller can tell them apart."""
        user_id = await _make_user(db_session, "off-named@example.com", is_active=False)

        body = (await async_client.patch(f"/users/{user_id}/deactivate")).json()

        assert user_id in body["detail"]

    async def test_conflict_does_not_touch_the_user(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-003: the rejected request leaves the record as it found it."""
        user_id = await _make_user(db_session, "untouched@example.com", is_active=False)

        assert (
            await async_client.patch(f"/users/{user_id}/deactivate")
        ).status_code == HTTPStatus.CONFLICT

        follow_up = await async_client.get(f"/users/{user_id}")

        assert follow_up.status_code == HTTPStatus.OK
        assert follow_up.json()["is_active"] is False


class TestDeactivateWhenTheDatabaseFails:
    """The dependency-down path: a 503, never a 200 that did not write."""

    async def test_unreachable_database_returns_503(
        self, async_client: AsyncClient
    ) -> None:
        """A session that cannot answer is an operational failure, not a 404."""

        async def broken_session() -> AsyncGenerator[AsyncSession, None]:
            session = AsyncMock(spec=AsyncSession)
            session.execute.side_effect = sqlalchemy_exc.OperationalError(
                "connection refused", {}, None
            )
            yield session

        app.dependency_overrides[app_get_db] = broken_session
        try:
            response = await async_client.patch(f"/users/{uuid4()}/deactivate")
        finally:
            app.dependency_overrides.pop(app_get_db, None)

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert "Database unavailable" in response.json()["detail"]

    async def test_failed_write_returns_503_not_a_lying_200(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """The write failing after the read is translated, not reported as done.

        The write itself moved into ``crud.deactivate_user`` (TASK-2FDE-002),
        so that is the operation made to fail here; what is asserted is
        unchanged.
        """
        user_id = await _make_user(db_session, "write-fails@example.com")

        with patch(
            "src.users.router.crud.deactivate_user",
            side_effect=sqlalchemy_exc.SQLAlchemyError("write failed"),
        ):
            response = await async_client.patch(f"/users/{user_id}/deactivate")

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert "Database unavailable" in response.json()["detail"]


class TestDeactivateDocumentation:
    """AC-004: the route and its three answers are in the published docs."""

    async def test_openapi_documents_the_route_and_its_answers(
        self, async_client: AsyncClient
    ) -> None:
        """AC-004: the generated OpenAPI document carries the contract."""
        openapi = (await async_client.get("/openapi.json")).json()

        operation = _operation(openapi)
        # The tag is set both on the route and on include_router in src/main.py,
        # exactly as every other users route does, so it is the set that matters.
        assert set(operation["tags"]) == {"users"}
        assert operation["summary"]
        assert operation["description"]
        assert {"200", "404", "409"} <= set(operation["responses"])
        for status in ("200", "404", "409"):
            assert operation["responses"][status]["description"]

    async def test_documented_success_body_is_the_user_shape(
        self, async_client: AsyncClient
    ) -> None:
        """AC-004: the documented 200 body is the user response, not a message."""
        openapi = (await async_client.get("/openapi.json")).json()

        schema = _resolved_schema(
            openapi,
            openapi["paths"]["/users/{user_id}/deactivate"]["patch"]["responses"][
                "200"
            ]["content"]["application/json"]["schema"],
        )

        assert {"id", "email", "is_active"} <= set(schema["properties"])
        assert schema["properties"]["is_active"]["type"] == "boolean"
