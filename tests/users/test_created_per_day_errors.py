"""Error-handling tests for ``GET /users/created-per-day`` (TASK-54E1-004).

Two invariants, one class each:

* AC-001 — when the database is unavailable the endpoint answers 503, whether
  the failure surfaces inside the query or before a session can be handed over,
  and the outage never reaches the caller as a 500 or as driver internals.
* AC-002 — that 503 body has the same shape as every other error this service
  raises: the one ``{"detail": "..."}`` body ``docs/API.md`` documents.

AC-003 (lint/format) is settled by ``ruff check`` and ``ruff format --check``
over the changed files, not by a test.

Owned elsewhere in FEAT-54E1, deliberately not re-pinned here: the SQL query
and its day bucketing (TASK-54E1-001, ``tests/users/test_created_per_day_counts.py``),
the endpoint itself (TASK-54E1-002, ``src/users/router.py``), the seven ordered
data points and the non-GET refusal (TASK-54E1-003,
``tests/users/test_daily_counts.py``), and the prose under ``docs/``
(TASK-54E1-005). One thing is excluded from the "every error looks the same"
invariant on purpose: FastAPI's own 422 request-validation body, whose
``detail`` is a list of field errors. No task in this feature changes it and
``tests/users/test_create_user_validation.py`` already pins it, so this file
checks the shape of errors the application raises itself.

These tests read no environment variables; which database the run talks to is
settled once in ``tests/__init__.py`` and arrives through the ``db_session``
and ``override_get_db`` fixtures.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator
from contextlib import ExitStack
from http import HTTPStatus
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.exc import (
    DBAPIError,
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.exc import (
    TimeoutError as SQLATimeoutError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    AppError,
    DatabaseUnavailableError,
    app_error_handler,
    error_body,
    sqlalchemy_error_handler,
)
from src.db.dependencies import get_db as app_get_db
from src.main import app
from src.users import crud

ENDPOINT = "/users/created-per-day"

WINDOW_DAYS = 7

# What a driver says when it cannot reach the server. "db.internal" is the
# sentinel the leak checks look for: it must appear in the log, never in a body.
DRIVER_MESSAGE = (
    'connection to server at "db.internal", port 5432 failed: Connection refused'
)

# Errors the routes catch (every one is a SQLAlchemyError), plus the base class.
DATABASE_ERROR_CLASSES: list[type[SQLAlchemyError]] = [
    SQLAlchemyError,
    OperationalError,
    DBAPIError,
    InterfaceError,
    SQLATimeoutError,
]


def _database_error(error_class: type[SQLAlchemyError]) -> SQLAlchemyError:
    """Build one failure of the requested SQLAlchemy error class.

    Args:
        error_class: The class to raise, all of which are SQLAlchemyError.

    Returns:
        SQLAlchemyError: An instance whose message is ``DRIVER_MESSAGE``.
            For the driver-level classes the message rides in as the original
            DB-API error, which is how a real driver failure arrives.
    """
    if issubclass(error_class, DBAPIError):
        return error_class(
            DRIVER_MESSAGE,
            {},
            ConnectionRefusedError(DRIVER_MESSAGE),
        )
    return error_class(DRIVER_MESSAGE)


def _driver_failure() -> OperationalError:
    """Build the error an unreachable database raises on a query.

    Returns:
        OperationalError: A driver-shaped failure carrying ``DRIVER_MESSAGE``.
    """
    return OperationalError(DRIVER_MESSAGE, {}, ConnectionRefusedError(DRIVER_MESSAGE))


async def _query_failing_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session whose queries fail the way an unreachable server fails.

    Yields:
        AsyncSession: A stand-in session that raises on ``execute``.
    """
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = _driver_failure()
    yield session


async def _session_cannot_be_opened() -> AsyncGenerator[AsyncSession, None]:
    """Refuse to hand over a session at all.

    The failure happens while the dependency runs, so no route body executes
    and no route-level ``except`` can see it: only a registered handler can.

    Yields:
        AsyncSession: Never reached.
    """
    raise _driver_failure()
    yield AsyncSession()  # pragma: no cover - makes this a generator


@pytest.fixture
def broken_database() -> Iterator[None]:
    """Point the session dependency at a database that fails every query.

    Yields:
        None: While the override is installed; removed afterwards.
    """
    app.dependency_overrides[app_get_db] = _query_failing_session
    yield
    app.dependency_overrides.pop(app_get_db, None)


@pytest.fixture
def unreachable_database() -> Iterator[None]:
    """Point the session dependency at a database that refuses connections.

    Yields:
        None: While the override is installed; removed afterwards.
    """
    app.dependency_overrides[app_get_db] = _session_cannot_be_opened
    yield
    app.dependency_overrides.pop(app_get_db, None)


def _body_keys(response: Response) -> set[str]:
    """Return the JSON keys of an error response body.

    Args:
        response: The response received.

    Returns:
        set[str]: The keys of the decoded body.

    Raises:
        AssertionError: When the body is not a JSON object.
    """
    body = response.json()
    assert isinstance(body, dict), f"body is not a JSON object: {body!r}"
    return set(body)


class TestDatabaseUnavailableReturns503:
    """AC-001: an unavailable database is answered with 503, never worse."""

    async def test_a_query_failure_returns_503(
        self,
        async_client: AsyncClient,
        broken_database: None,
    ) -> None:
        """AC-001: a query that fails because the database is down gives 503."""
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert "database unavailable" in response.json()["detail"].lower()

    @pytest.mark.parametrize("error_class", DATABASE_ERROR_CLASSES)
    async def test_every_database_error_class_returns_503(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        error_class: type[SQLAlchemyError],
    ) -> None:
        """AC-001: no shape of database failure escapes as a 500.

        Every class here descends from the ``SQLAlchemyError`` the endpoint
        catches, so the answer must not depend on which one the driver raised.
        """
        with patch.object(crud, "count_users_created_per_day") as counter:
            counter.side_effect = _database_error(error_class)

            response = await async_client.get(ENDPOINT)

            assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE, error_class

    async def test_an_unreachable_database_returns_503(
        self,
        async_client: AsyncClient,
        broken_database: None,
    ) -> None:
        """AC-001: a real session failure, with nothing patched in the route.

        The query goes to the injected session and fails there, which is what
        happens when the server behind ``DATABASE_URL`` is down.
        """
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE

    async def test_a_database_that_refuses_the_session_returns_503(
        self,
        async_client: AsyncClient,
        unreachable_database: None,
    ) -> None:
        """AC-001: the handler answers even when no route body runs.

        Here the dependency itself fails, so the endpoint's own ``except``
        never executes. The registered handler is what keeps this a 503
        rather than an unhandled exception.
        """
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert response.json() == error_body(DatabaseUnavailableError.default_detail)

    async def test_the_outage_is_not_reported_as_a_server_error(
        self,
        async_client: AsyncClient,
        broken_database: None,
    ) -> None:
        """AC-001: 503 says "try again", a 500 would say "we are broken"."""
        response = await async_client.get(ENDPOINT)

        assert response.status_code != HTTPStatus.INTERNAL_SERVER_ERROR
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE

    async def test_the_body_names_the_condition_not_the_driver(
        self,
        async_client: AsyncClient,
        broken_database: None,
    ) -> None:
        """AC-001: the caller is told what to do, not what the wire said.

        ``DRIVER_MESSAGE`` names a host and a port. It belongs in the log; in
        a response body it is an internals leak and a different 503 per
        endpoint, which is what AC-002 rules out.
        """
        response = await async_client.get(ENDPOINT)

        assert DRIVER_MESSAGE not in response.text
        assert "db.internal" not in response.text
        assert "database unavailable" in response.json()["detail"].lower()

    async def test_no_data_points_are_returned_with_a_failure(
        self,
        async_client: AsyncClient,
        broken_database: None,
    ) -> None:
        """AC-001: an outage never pretends to be a count of zeros."""
        response = await async_client.get(ENDPOINT)

        body = response.json()
        assert isinstance(body, dict)
        assert "count" not in str(body)
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE

    async def test_an_outage_does_not_wedge_the_endpoint(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        broken_database: None,
    ) -> None:
        """AC-001: the 503 is per request, not a latch the app remembers."""

        async def healthy_session() -> AsyncGenerator[AsyncSession, None]:
            yield db_session

        failed = await async_client.get(ENDPOINT)
        assert failed.status_code == HTTPStatus.SERVICE_UNAVAILABLE

        app.dependency_overrides[app_get_db] = healthy_session
        recovered = await async_client.get(ENDPOINT)

        assert recovered.status_code == HTTPStatus.OK
        assert len(recovered.json()) == WINDOW_DAYS

    async def test_the_error_response_still_carries_the_api_headers(
        self,
        async_client: AsyncClient,
        broken_database: None,
    ) -> None:
        """AC-001: a 503 is still a response this service sent.

        It carries the correlation id and API version that every other
        response carries, so a caller can line the failure up with the log.
        """
        response = await async_client.get(ENDPOINT)

        assert response.headers["x-correlation-id"]
        assert response.headers["x-api-version"]


class TestConsistentErrorFormat:
    """AC-002: every error this service raises wears the same body."""

    async def test_the_same_outage_reads_identically_on_every_count_endpoint(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """AC-002: one failure, one message, on every endpoint that counts.

        The bodies must be equal to each other, not merely similar: a 503 that
        quotes the driver would differ per endpoint and per exception.
        """
        paths = [
            ENDPOINT,
            "/users/count",
            "/users/count-today",
            "/users/count-by-domain",
            "/users",
        ]

        with ExitStack() as stack:
            for name in (
                "count_users_created_per_day",
                "count_users",
                "count_users_today",
                "count_users_by_domain",
                "get_users",
            ):
                mock = stack.enter_context(patch.object(crud, name))
                mock.side_effect = SQLAlchemyError(DRIVER_MESSAGE)

            responses = [await async_client.get(path) for path in paths]

        statuses = [response.status_code for response in responses]
        bodies = [response.json() for response in responses]

        assert statuses == [int(HTTPStatus.SERVICE_UNAVAILABLE)] * len(paths)
        assert bodies == [bodies[0]] * len(bodies)
        assert bodies[0] == error_body(DatabaseUnavailableError.default_detail)

    @pytest.mark.parametrize(
        ("method", "path", "expected_status"),
        [
            ("GET", "/users/{user_id}", HTTPStatus.NOT_FOUND),
            ("POST", ENDPOINT, HTTPStatus.METHOD_NOT_ALLOWED),
            ("GET", "/users/count-by-domain?min_count=-1", HTTPStatus.BAD_REQUEST),
        ],
    )
    async def test_errors_raised_by_the_app_share_one_body_shape(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        method: str,
        path: str,
        expected_status: HTTPStatus,
    ) -> None:
        """AC-002: a 400, a 404 and a 405 all carry one detail string."""
        if "{user_id}" in path:
            path = path.replace("{user_id}", str(uuid4()))

        response = await async_client.request(method, path)

        assert response.status_code == expected_status, path
        assert response.headers["content-type"].startswith("application/json")
        assert _body_keys(response) == {"detail"}
        assert isinstance(response.json()["detail"], str)
        assert response.json()["detail"]

    async def test_the_database_failure_bodies_match_the_other_errors(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """AC-002: the 503 body is keyed and typed exactly like a 404 body."""
        missing = await async_client.get(f"/users/{uuid4()}")
        with patch.object(crud, "count_users_created_per_day") as counter:
            counter.side_effect = SQLAlchemyError(DRIVER_MESSAGE)
            failed = await async_client.get(ENDPOINT)

        assert missing.status_code == HTTPStatus.NOT_FOUND
        assert failed.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert _body_keys(missing) == _body_keys(failed) == {"detail"}
        for body in (missing.json(), failed.json()):
            assert isinstance(body["detail"], str)
            assert body["detail"]

    def test_the_body_builder_produces_the_documented_shape(self) -> None:
        """AC-002: ``docs/API.md``'s ``{"detail": "..."}`` is what we emit."""
        assert error_body("anything") == {"detail": "anything"}
        assert set(error_body("anything")) == {"detail"}

    def test_the_database_error_carries_one_status_and_one_message(self) -> None:
        """AC-002: raising the error twice cannot produce two different 503s."""
        assert DatabaseUnavailableError.status_code == int(
            HTTPStatus.SERVICE_UNAVAILABLE
        )
        assert issubclass(DatabaseUnavailableError, AppError)
        assert DatabaseUnavailableError().detail == DatabaseUnavailableError().detail
        assert DatabaseUnavailableError().detail == (
            DatabaseUnavailableError.default_detail
        )

    def test_the_application_registers_the_error_handlers(self) -> None:
        """AC-002: the translation lives on the app, not in one route.

        ``AppError`` covers its subclasses; ``SQLAlchemyError`` is the net for a
        database error no route caught. Without either, a 503 would depend on
        which route the request landed in.
        """
        handlers = app.exception_handlers

        assert handlers.get(AppError) is app_error_handler
        assert handlers.get(DatabaseUnavailableError) is app_error_handler
        assert handlers.get(SQLAlchemyError) is sqlalchemy_error_handler


class TestNoDatabaseAccessOnTheRejectionPaths:
    """AC-002's corollary: an error raised before the query stays cheap."""

    async def test_a_refused_method_never_touches_the_database(
        self,
        async_client: AsyncClient,
        unreachable_database: None,
    ) -> None:
        """AC-002: a 405 is a 405 whatever the database is doing.

        With the database refusing every request, the method refusal must still
        answer 405 — if it reached the database instead, the failure would
        arrive as a 503 and the two error paths would be indistinguishable.
        """
        response = await async_client.post(ENDPOINT)

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
        assert _body_keys(response) == {"detail"}
