"""Tests for the analytics router (TASK-6F3D-003).

Covers the acceptance criteria of TASK-6F3D-003:

- AC-001: ``GET /users/created-per-day`` is implemented and answers the last
  seven days of user creations, oldest first, over HTTP
- AC-002: the response body matches the Pydantic schema
  (``src.analytics.schemas.CreatedPerDayResponse``)
- AC-003: the files this task modified pass the project-configured lint and
  format checks (``ruff check`` and ``ruff format --check``, as pyproject.toml
  configures them) with zero errors

The tests go through the ASGI app rather than calling the handler, so what is
graded is the route a caller reaches: its path, its method set, the session
injected into it, and the JSON that leaves it. They run against whichever
database the harness settled for the run — in-memory SQLite by default,
PostgreSQL under qa/run-suite.sh.
"""

from __future__ import annotations

import inspect
import json
import logging
import subprocess
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.analytics import router as analytics_router
from src.analytics.schemas import CreatedPerDayResponse
from src.main import app
from src.users import crud
from src.users.schemas import UserCreate

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: The endpoint under test, and the file that serves it.
ENDPOINT = "/users/created-per-day"

#: The files TASK-6F3D-003 writes: the new router, and the application module
#: that registers it.
MODIFIED_FILES = ("src/analytics/router.py", "src/main.py")

#: Days in the window the endpoint promises, restated here so the tests fail if
#: the implementation quietly widens or narrows it.
WINDOW_DAYS = 7


def utc_today() -> date:
    """Today's UTC date, derived rather than imported.

    Importing ``src.analytics.crud.utc_today`` would grade the implementation
    against itself, so the tests take the day the way the feature spec
    describes it: the current day in UTC.

    Returns:
        date: The current UTC calendar day.
    """
    return datetime.now(tz=UTC).date()


def at_noon(day: date) -> datetime:
    """A timestamp in the middle of a day, so no window edge is being probed.

    Args:
        day: The calendar day to place the timestamp on.

    Returns:
        datetime: Noon on ``day``, naive, as ``users.created_at`` stores it.
    """
    return datetime(day.year, day.month, day.day, 12, 0)


async def seed_users_on_day(
    db: AsyncSession, local_part: str, day: date, count: int
) -> None:
    """Create ``count`` users whose creation timestamp falls on ``day``.

    Args:
        db: The session to write through.
        local_part: Prefix for the generated email addresses, so repeated
            calls on different days do not collide on the unique email.
        day: The calendar day to stamp the rows with.
        count: How many users to create.
    """
    for index in range(count):
        user = await crud.create_user(
            db,
            UserCreate(
                email=f"{local_part}-{index}-{day.isoformat()}@example.com",
                full_name="Seeded",
            ),
        )
        user.created_at = at_noon(day)
        await db.flush()
        await db.refresh(user)


def _tool(name: str) -> list[str]:
    """The command line that runs a project-configured tool.

    Args:
        name: The tool's executable name, e.g. ``"ruff"``.

    Returns:
        list[str]: The command, preferring the project's own virtualenv.
    """
    local = PROJECT_ROOT / ".venv" / "bin" / name
    if local.exists():
        return [str(local)]
    return [sys.executable, "-m", name]  # pragma: no cover - fallback


def dates_of(body: object) -> list[date]:
    """The data points' dates, read from the decoded JSON body.

    Args:
        body: The decoded response body, a list of data points.

    Returns:
        list[date]: The dates in the order the response sent them.
    """
    assert isinstance(body, list)
    return [date.fromisoformat(point["date"]) for point in body]


def exposed_routes(routes: Iterable[Any]) -> set[tuple[str, frozenset[str]]]:
    """Every (path, methods) pair the application answers, routers unwrapped.

    Args:
        routes: The routes to walk, as ``app.routes`` gives them. FastAPI
            keeps an included router behind a wrapper rather than flattening
            its routes into the list, so the wrapper is opened here.

    Returns:
        set[tuple[str, frozenset[str]]]: The address of each endpoint, with
        the methods it accepts.
    """
    found: set[tuple[str, frozenset[str]]] = set()
    for route in routes:
        nested = getattr(route, "routes", None) or getattr(
            getattr(route, "original_router", None), "routes", None
        )
        if nested:
            found |= exposed_routes(nested)
            continue
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path and methods:
            found.add((path, frozenset(methods)))
    return found


def resolve_ref(
    schema: Mapping[str, Any], components: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Follow a ``$ref`` to the component it names, if it is one.

    Args:
        schema: The schema that may point at a component.
        components: The OpenAPI ``components/schemas`` mapping.

    Returns:
        Mapping[str, Any]: The referenced component, or the schema itself when
        it carries no reference.
    """
    reference = schema.get("$ref")
    if not isinstance(reference, str):
        return schema
    return components[reference.rsplit("/", maxsplit=1)[-1]]


class TestRouteIsExposed:
    """AC-001: the endpoint exists, answers GET, and rejects other methods."""

    async def test_get_returns_success(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """A plain GET to the endpoint succeeds."""
        response = await async_client.get(ENDPOINT)
        assert response.status_code == HTTPStatus.OK

    async def test_endpoint_is_registered_on_the_app(self) -> None:
        """The route is part of the application, not only of its own router."""
        assert (ENDPOINT, frozenset({"GET"})) in exposed_routes(app.routes)

    async def test_post_is_rejected_with_method_not_allowed(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The endpoint is read-only: POST is not allowed on it."""
        response = await async_client.post(ENDPOINT, json={})
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    async def test_handler_is_async(self) -> None:
        """The route handler is an ``async def``, as the task requires."""
        from src.analytics.router import get_created_per_day

        assert inspect.iscoroutinefunction(get_created_per_day)


class TestSevenDaysOverHttp:
    """AC-001: the reply is the last seven days, oldest first."""

    async def test_exactly_seven_data_points(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Seven data points come back when the database holds nothing."""
        response = await async_client.get(ENDPOINT)
        assert len(response.json()) == WINDOW_DAYS

    async def test_never_more_than_seven_data_points(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Users far outside the window do not lengthen the reply."""
        today = utc_today()
        await seed_users_on_day(db_session, "long-ago", today - timedelta(days=40), 3)
        await seed_users_on_day(db_session, "in-window", today, 2)

        response = await async_client.get(ENDPOINT)
        assert len(response.json()) == WINDOW_DAYS

    async def test_window_is_the_seven_days_ending_today(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The days are today and the six before it, oldest first."""
        today = utc_today()
        expected = [
            today - timedelta(days=offset) for offset in range(WINDOW_DAYS - 1, -1, -1)
        ]

        response = await async_client.get(ENDPOINT)
        assert dates_of(response.json()) == expected

    async def test_data_points_are_strictly_ascending(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Each data point falls strictly later than the one before it."""
        response = await async_client.get(ENDPOINT)
        days = dates_of(response.json())
        assert all(
            later > earlier for earlier, later in zip(days, days[1:], strict=False)
        )

    async def test_counts_are_non_negative_integers(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Every count is an ``int`` that is zero or greater."""
        today = utc_today()
        await seed_users_on_day(db_session, "seeded", today - timedelta(days=2), 3)

        response = await async_client.get(ENDPOINT)
        body = response.json()
        assert isinstance(body, list)
        for point in body:
            assert isinstance(point["count"], int)
            assert point["count"] >= 0

    async def test_seeded_days_are_counted_and_other_days_are_zero(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """The window carries the seeded counts, and empty days read as zero."""
        today = utc_today()
        await seed_users_on_day(
            db_session, "two-days-ago", today - timedelta(days=2), 4
        )
        await seed_users_on_day(db_session, "today", today, 1)

        response = await async_client.get(ENDPOINT)
        body = response.json()
        assert isinstance(body, list)
        counts = {point["date"]: point["count"] for point in body}
        assert counts[(today - timedelta(days=2)).isoformat()] == 4
        assert counts[today.isoformat()] == 1
        assert counts[(today - timedelta(days=4)).isoformat()] == 0

    async def test_empty_database_answers_seven_zero_counts(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """With no users at all the endpoint still answers seven days of zeros."""
        response = await async_client.get(ENDPOINT)
        body = response.json()
        assert isinstance(body, list)
        assert [point["count"] for point in body] == [0] * WINDOW_DAYS

    async def test_soft_deleted_users_are_not_counted(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """A deleted user is not a creation the analytics reports today."""
        today = utc_today()
        user = await crud.create_user(
            db_session, UserCreate(email="deleted-today@example.com", full_name="Gone")
        )
        user.created_at = at_noon(today)
        user.deleted_at = at_noon(today)
        await db_session.flush()

        response = await async_client.get(ENDPOINT)
        body = response.json()
        assert isinstance(body, list)
        assert body[-1]["count"] == 0


class TestDatabaseUnavailable:
    """The dependency-down path named in the task's pass bar.

    A failed query must not answer a short or partial series: the caller is
    told the service is unavailable and can retry.
    """

    async def test_query_failure_answers_service_unavailable(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A database error becomes 503, not a truncated series or a 500."""

        async def refuse(*_args: object, **_kwargs: object) -> CreatedPerDayResponse:
            """Stand in for the query layer with a database that refuses."""
            raise SQLAlchemyError("database refused the daily-count query")

        monkeypatch.setattr(analytics_router, "get_users_created_per_day", refuse)

        response = await async_client.get(ENDPOINT)
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert "Database unavailable" in response.json()["detail"]

    async def test_query_failure_is_logged(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The failure is reported, not swallowed on the way to the 503."""

        async def refuse(*_args: object, **_kwargs: object) -> CreatedPerDayResponse:
            """Stand in for the query layer with a database that fails."""
            raise SQLAlchemyError("connection reset by peer")

        monkeypatch.setattr(analytics_router, "get_users_created_per_day", refuse)

        with caplog.at_level(logging.ERROR, logger="src.analytics.router"):
            response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert any(
            "SQLAlchemyError" in record.getMessage() for record in caplog.records
        )


class TestResponseMatchesSchema:
    """AC-002: the body is exactly what ``CreatedPerDayResponse`` describes."""

    async def test_body_validates_against_the_response_schema(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """The decoded JSON round-trips through the Pydantic model."""
        today = utc_today()
        await seed_users_on_day(db_session, "schema", today - timedelta(days=1), 2)

        response = await async_client.get(ENDPOINT)
        parsed = CreatedPerDayResponse.model_validate(response.json())
        assert len(parsed.root) == WINDOW_DAYS

    async def test_body_is_a_bare_json_array_of_date_and_count(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The contract is a bare array of ``{date, count}`` objects."""
        response = await async_client.get(ENDPOINT)
        body = json.loads(response.text)
        assert isinstance(body, list)
        assert body, "the response array is never empty"
        for point in body:
            assert set(point) == {"date", "count"}

    async def test_dates_are_iso_8601_calendar_days(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Each date is serialised as ``YYYY-MM-DD``, no time component."""
        response = await async_client.get(ENDPOINT)
        body = response.json()
        assert isinstance(body, list)
        for point in body:
            assert len(point["date"]) == len("2026-09-14")
            assert date.fromisoformat(point["date"]).isoformat() == point["date"]

    def test_openapi_documents_the_endpoint_and_its_schema(self) -> None:
        """The generated OpenAPI names the path and the data-point shape."""
        schema: dict = app.openapi()
        assert ENDPOINT in schema["paths"]
        response_schema: dict = schema["paths"][ENDPOINT]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        components: dict = schema["components"]["schemas"]
        series = resolve_ref(response_schema, components)
        assert series["type"] == "array"
        data_point = resolve_ref(series["items"], components)
        properties: dict = data_point["properties"]
        assert set(properties) == {"date", "count"}
        assert properties["count"]["minimum"] == 0


class TestLintAndFormat:
    """AC-003: the modified files pass the project-configured checks."""

    def test_ruff_check_reports_no_errors(self) -> None:
        """`ruff check` (E, F, I, UP per pyproject) is clean on both files."""
        result = subprocess.run(
            [*_tool("ruff"), "check", *MODIFIED_FILES],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_ruff_format_reports_no_rewrites(self) -> None:
        """`ruff format --check` would leave both files untouched."""
        result = subprocess.run(
            [*_tool("ruff"), "format", "--check", *MODIFIED_FILES],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
