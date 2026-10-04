"""Endpoint tests for ``PATCH /users/{user_id}/deactivate`` (TASK-2FDE-003, FEAT-2FDE).

The route and the CRUD layer underneath it already exist (TASK-2FDE-001 and
TASK-2FDE-002). This file is the deactivation feature's own account of what the
endpoint promises, taken scenario by scenario from
``features/deactivate-user/deactivate-user.feature``, and every one of them is
asked of the running application over HTTP rather than of a function.

Two scenarios need more than the shared ``override_get_db`` session can give:

* two requests at once cannot share one ``AsyncSession``, so that class uses
  ``per_request_sessions`` below, which opens a session for each request;
* a write that has to be seen by a session other than the one that made it
  cannot live inside the ``db_session`` fixture's rollback-only transaction, so
  the same fixture is used wherever a test reads the row back afterwards.

Both replace the same seam the suite always uses —
``src.db.dependencies.get_db`` — so the application under test is unchanged.

The database boundary is pinned twice over: once by asking the route to
deactivate against a session that cannot answer (the mocked service-unavailable
case), and once by checking that the route goes through that dependency for its
session at all, which is the only reason the rest of these tests test anything.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from http import HTTPStatus
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.db.dependencies import get_db as app_get_db
from src.main import app
from src.users import crud
from src.users.schemas import UserCreate, UserUpdate


async def _make_user(db: AsyncSession, email: str, *, is_active: bool = True) -> str:
    """Create one live user through the application's own CRUD layer.

    Args:
        db: The session the row is written with.
        email: The address of the user to create.
        is_active: Whether the user is left active; pass False for a user who
            was deactivated before the request under test.

    Returns:
        str: The new user's id.
    """
    user = await crud.create_user(db, UserCreate(email=email))
    if not is_active:
        updated = await crud.update_user(db, str(user.id), UserUpdate(is_active=False))
        assert updated is not None
        return str(updated.id)
    return str(user.id)


@pytest.fixture
async def per_request_sessions(db_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    """Hand each request its own session on this test's engine, and really commit.

    ``override_get_db`` gives every request the same session, which is what a
    test making one request wants. Two requests at once cannot share an
    ``AsyncSession``, and nothing written inside the ``db_session`` fixture's
    transaction can be seen by another session, so this overrides the same
    dependency with one that opens a session per request. The rows are
    committed for real; the test's own schema is dropped when the test ends.

    Args:
        db_engine: The engine this test's schema and tables live on.

    Yields:
        None: While the override is in place.
    """
    sessions = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async def get_db_per_request() -> AsyncGenerator[AsyncSession, None]:
        async with sessions() as session:
            yield session

    app.dependency_overrides[app_get_db] = get_db_per_request
    try:
        yield
    finally:
        app.dependency_overrides.pop(app_get_db, None)


class TestDeactivatingAnActiveUser:
    """AC-001: "Deactivating an active user succeeds"."""

    async def test_answers_200_with_the_updated_user(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-001: the user comes back inactive, and is otherwise themselves."""
        user_id = await _make_user(db_session, "deactivate-me@example.com")

        response = await async_client.patch(f"/users/{user_id}/deactivate")

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["id"] == user_id
        assert body["email"] == "deactivate-me@example.com"
        assert body["is_active"] is False

    async def test_the_next_request_reports_the_same_user(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-001: the 200 is honest — the follow-up GET says inactive too."""
        user_id = await _make_user(db_session, "seen-again@example.com")

        assert (
            await async_client.patch(f"/users/{user_id}/deactivate")
        ).status_code == HTTPStatus.OK

        follow_up = await async_client.get(f"/users/{user_id}")

        assert follow_up.status_code == HTTPStatus.OK
        assert follow_up.json()["is_active"] is False

    async def test_the_deactivation_is_written_down(
        self,
        async_client: AsyncClient,
        db_engine: AsyncEngine,
        per_request_sessions: None,
    ) -> None:
        """AC-001: a session that never made the write reads the row back inactive.

        The session dependency does not commit, so a deactivation that was only
        intended and never written would still read back inactive inside the
        request that attempted it. This is the one shape of the happy path that
        can tell the two apart.
        """
        sessions = async_sessionmaker(bind=db_engine, expire_on_commit=False)
        async with sessions() as writing:
            user_id = await _make_user(writing, "written-down@example.com")

        response = await async_client.patch(f"/users/{user_id}/deactivate")

        assert response.status_code == HTTPStatus.OK
        assert response.json()["is_active"] is False

        async with sessions() as reading:
            found = await crud.get_user(reading, user_id)

        assert found is not None, (
            "no live row after a 200: the deactivation was never written down"
        )
        assert found.is_active is False


class TestDeactivatingAUserThatIsNotThere:
    """AC-002: "Deactivating a non-existent user returns not found"."""

    async def test_an_unknown_id_answers_404(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-002: a well-formed id nobody holds is missing, not a silent no-op."""
        missing = str(uuid4())

        response = await async_client.patch(f"/users/{missing}/deactivate")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert missing in response.json()["detail"]

    async def test_a_soft_deleted_user_answers_404(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-002: a deleted row is not a user this route may act on."""
        user_id = await _make_user(db_session, "already-deleted@example.com")
        assert await crud.delete_user(db_session, user_id) is True

        response = await async_client.patch(f"/users/{user_id}/deactivate")

        assert response.status_code == HTTPStatus.NOT_FOUND

    async def test_a_deactivation_never_creates_the_user_it_was_given(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-002: the 404 leaves nothing behind — the id is still nobody's."""
        missing = str(uuid4())

        assert (
            await async_client.patch(f"/users/{missing}/deactivate")
        ).status_code == HTTPStatus.NOT_FOUND

        follow_up = await async_client.get(f"/users/{missing}")

        assert follow_up.status_code == HTTPStatus.NOT_FOUND


class TestDeactivatingAnAlreadyInactiveUser:
    """AC-003: "Deactivating an already inactive user returns conflict"."""

    async def test_an_inactive_user_answers_409(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-003: repeating the request conflicts rather than succeeding again."""
        user_id = await _make_user(
            db_session, "already-off@example.com", is_active=False
        )

        response = await async_client.patch(f"/users/{user_id}/deactivate")

        assert response.status_code == HTTPStatus.CONFLICT
        assert "detail" in response.json()

    async def test_the_conflict_names_the_user_it_was_asked_about(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-003: the answer says which user, so a caller can tell them apart."""
        user_id = await _make_user(db_session, "off-named@example.com", is_active=False)

        body = (await async_client.patch(f"/users/{user_id}/deactivate")).json()

        assert user_id in body["detail"]

    async def test_the_rejected_request_leaves_the_user_exactly_as_it_was(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-003: a conflict is a refusal, so the user must not move at all."""
        user_id = await _make_user(db_session, "untouched@example.com", is_active=False)
        before = (await async_client.get(f"/users/{user_id}")).json()

        assert (
            await async_client.patch(f"/users/{user_id}/deactivate")
        ).status_code == HTTPStatus.CONFLICT

        after = (await async_client.get(f"/users/{user_id}")).json()

        assert after == before

    async def test_a_user_deactivated_by_an_earlier_request_answers_409(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-003: the second of two sequential requests is the conflict case."""
        user_id = await _make_user(db_session, "twice-running@example.com")

        assert (
            await async_client.patch(f"/users/{user_id}/deactivate")
        ).status_code == HTTPStatus.OK
        second = await async_client.patch(f"/users/{user_id}/deactivate")

        assert second.status_code == HTTPStatus.CONFLICT


class TestTwoSimultaneousDeactivations:
    """AC-004: "Concurrent deactivation requests are handled gracefully"."""

    async def test_one_request_succeeds_and_the_other_conflicts(
        self,
        async_client: AsyncClient,
        db_engine: AsyncEngine,
        per_request_sessions: None,
    ) -> None:
        """AC-004: of two requests at once, exactly one deactivates the user.

        Each request has its own session, so this is the real race rather than
        one session used twice. Whichever order the two are served in, the
        answer cannot be 200 twice: that would mean the same deactivation was
        reported as a change by both callers.
        """
        sessions = async_sessionmaker(bind=db_engine, expire_on_commit=False)
        async with sessions() as writing:
            user_id = await _make_user(writing, "two-at-once@example.com")

        first, second = await asyncio.gather(
            async_client.patch(f"/users/{user_id}/deactivate"),
            async_client.patch(f"/users/{user_id}/deactivate"),
        )

        statuses = sorted(response.status_code for response in (first, second))
        assert statuses == [HTTPStatus.OK, HTTPStatus.CONFLICT], (
            "two simultaneous deactivations did not split into one change and "
            f"one conflict: {statuses}"
        )

        by_status = {response.status_code: response for response in (first, second)}
        assert by_status[HTTPStatus.OK].json()["is_active"] is False
        assert user_id in by_status[HTTPStatus.CONFLICT].json()["detail"]

    async def test_the_user_ends_inactive_whichever_request_won(
        self,
        async_client: AsyncClient,
        db_engine: AsyncEngine,
        per_request_sessions: None,
    ) -> None:
        """AC-004: the row is left deactivated, and by a committed write.

        Read through a session that took no part in either request, so the
        result does not depend on which of the two won or on what either of
        them still holds in memory.
        """
        sessions = async_sessionmaker(bind=db_engine, expire_on_commit=False)
        async with sessions() as writing:
            user_id = await _make_user(writing, "racing@example.com")

        await asyncio.gather(
            *(async_client.patch(f"/users/{user_id}/deactivate") for _ in range(2))
        )

        async with sessions() as reading:
            found = await crud.get_user(reading, user_id)

        assert found is not None
        assert found.is_active is False


class TestDeactivationWhenTheUserServiceIsUnavailable:
    """AC-005: "Deactivation fails gracefully when the user service is unavailable"."""

    async def test_a_database_that_cannot_be_reached_answers_503(
        self, async_client: AsyncClient
    ) -> None:
        """AC-005: an unreachable store is an operational failure, never a 404.

        This is the seam test for the database boundary: the session is a mock,
        so the route's own translation of a dead database is what is being
        asked about, with nothing underneath to soften it.
        """

        async def unreachable_db() -> AsyncGenerator[AsyncSession, None]:
            session = AsyncMock(spec=AsyncSession)
            session.execute.side_effect = sqlalchemy_exc.OperationalError(
                "connection refused", {}, None
            )
            yield session

        previous = app.dependency_overrides.get(app_get_db)
        app.dependency_overrides[app_get_db] = unreachable_db
        try:
            response = await async_client.patch(f"/users/{uuid4()}/deactivate")
        finally:
            if previous is None:  # pragma: no cover - the fixture always sets one
                app.dependency_overrides.pop(app_get_db, None)
            else:
                app.dependency_overrides[app_get_db] = previous

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert "Database unavailable" in response.json()["detail"]

    async def test_a_write_that_fails_answers_503_and_not_a_lying_200(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-005: a failure at the database boundary is reported as one.

        The read has already succeeded here, so the only thing left to get
        wrong is claiming success for a change that never happened.
        """
        user_id = await _make_user(db_session, "write-fails@example.com")

        with patch(
            "src.users.router.crud.deactivate_user",
            side_effect=sqlalchemy_exc.SQLAlchemyError("write failed"),
        ):
            response = await async_client.patch(f"/users/{user_id}/deactivate")

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert "Database unavailable" in response.json()["detail"]

        still_there = await crud.get_user(db_session, user_id)
        assert still_there is not None
        assert still_there.is_active is True, (
            "the request reported failure, so the user must be as it found them"
        )

    async def test_the_route_asks_the_injected_dependency_for_its_session(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-005 (seam): the route's database access goes through get_db.

        Everything above depends on the route taking its session from
        ``src.db.dependencies.get_db``. A route that built an engine or a
        session of its own would pass the mocked cases by accident and talk to
        a live database in production, so the seam is asserted directly.
        """
        provided: list[str] = []
        previous = app.dependency_overrides[app_get_db]

        async def counting_get_db() -> AsyncGenerator[AsyncSession, None]:
            async for session in previous():
                provided.append("session")
                yield session

        app.dependency_overrides[app_get_db] = counting_get_db
        try:
            user_id = await _make_user(db_session, "through-the-seam@example.com")
            response = await async_client.patch(f"/users/{user_id}/deactivate")
        finally:
            app.dependency_overrides[app_get_db] = previous

        assert response.status_code == HTTPStatus.OK
        assert provided, (
            "the route answered a deactivate request without asking "
            "src.db.dependencies.get_db for a session"
        )
