"""Router tests for ``GET /users/created-per-day`` (TASK-D49B-003, FEAT-D49B).

What is pinned here is the *route*: that the application answers
``GET /users/created-per-day``, that the literal path is served by the daily-count
handler rather than swallowed by ``GET /users/{user_id}`` (whose route is declared
after it), and that the handler's database session arrives through the
application's dependency injection — ADR-006 and rule R-ADR006-1 in
docs/architecture-rules.yaml.

Owned elsewhere in this feature, and deliberately not restated here:

* the SQL and the window's arithmetic — TASK-D49B-002, in
  ``tests/users/test_stats_crud.py``;
* any further shaping of the endpoint's payload — TASK-D49B-004;
* ``tests/users/test_stats.py``, the endpoint test file, which TASK-D49B-005 owns.

So no test in this file asserts that a route, handler or file a later task of this
feature will add is absent; every assertion below is about behaviour this feature
is specified to keep. Expected dates are derived from ``date.today()``, the same
clock the read model uses, so the assertions hold on whichever day they run.

Requests go through an ASGI probe wrapper rather than the plain ``async_client``
fixture: the probe hands back the connection scope of the request it served, which
is where the resolved route and its solved dependency graph live. That keeps the
dependency-injection pins honest about the handler the application *actually*
routes to, wherever in ``src/users`` a later task may move it to.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from http import HTTPStatus
from typing import Any, cast

import pytest
from fastapi import Depends as DependsFactory
from fastapi.params import Depends as DependsClass
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_db as dependencies_get_db
from src.db.session import get_async_session
from src.db.session import get_db as session_get_db
from src.main import app
from src.users import crud
from src.users.schemas import UserCreate
from src.users.stats import DEFAULT_WINDOW_DAYS

ENDPOINT_PATH = "/users/created-per-day"

# The session providers this application recognises. A handler that asks FastAPI
# for any of them is following ADR-006; the suite's own override uses the first.
DB_SESSION_PROVIDERS = (dependencies_get_db, session_get_db, get_async_session)

_USERS_SOURCE_ROOT = pathlib.Path(__file__).resolve().parents[2] / "src" / "users"

# Constructing a session or an engine outside src/db is what ADR-006 forbids and
# what rule R-ADR006-1 looks for. ``get_async_session`` is on the list with them:
# entering it directly is this repository's way of taking a session into a handler
# without going through ``Depends``, which is the same forbidding seen from the
# other side.
_FORBIDDEN_SESSION_CALLS = frozenset(
    {
        "AsyncSession",
        "Session",
        "async_sessionmaker",
        "create_async_engine",
        "get_async_session",
        "init_engine",
        "sessionmaker",
    }
)

# ``fastapi.Depends`` is the marker class in some releases and a factory function
# returning a ``fastapi.params.Depends`` in others. Name whichever type actually
# marks a declared dependency in the release installed here.
_DEPENDS_TYPES: tuple[Any, ...] = (
    (DependsFactory,) if inspect.isclass(DependsFactory) else (DependsClass,)
)


class InjectionLog:
    """The sessions the application was handed through dependency injection."""

    def __init__(self) -> None:
        self.sessions: list[AsyncSession] = []

    @property
    def calls(self) -> int:
        """How many times a route asked the application for a session."""
        return len(self.sessions)


@asynccontextmanager
async def _probing_client() -> AsyncIterator[tuple[AsyncClient, dict[str, Any]]]:
    """Yield an ASGI client and the connection scope of the request it serves.

    Yields:
        A client, and the dict that ends up holding the served request's scope
        entries (``route``, ``endpoint``, ...).

    Raises:
        RuntimeError: If the wrapped application raises instead of answering.
    """
    scope_seen: dict[str, Any] = {}

    async def probe(scope: Any, receive: Any, send: Any) -> None:
        try:
            await app(scope, receive, send)
        finally:
            scope_seen.update(scope)

    transport = ASGITransport(app=probe)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, scope_seen


async def _get(client: AsyncClient, path: str = ENDPOINT_PATH) -> Response:
    """Issue one GET, so every test asks for the path the same way."""
    return await client.get(path)


def _route_of(scope: dict[str, Any]) -> Any:
    """Return the route the application matched for the probed request."""
    if "route" not in scope:
        pytest.fail(
            "The probed request never reached a route, so nothing about its "
            "registration or dependencies could be inspected. The path is "
            "probably not registered at all."
        )
    return scope["route"]


def _dependency_callables(dependant: Any, found: set[object]) -> None:
    """Collect every callable in a solved dependency graph, depth first.

    Args:
        dependant: A FastAPI ``Dependant``.
        found: The callables seen so far, updated in place.
    """
    call: object = getattr(dependant, "call", None)
    if call is not None:
        found.add(call)
    children: Sequence[Any] = getattr(dependant, "dependencies", ())
    for child in children:
        _dependency_callables(child, found)


def _providers_of(endpoint: Callable[..., Any]) -> set[object]:
    """Return the callables ``endpoint`` asks FastAPI to supply.

    Both styles the record allows are read: a ``Depends(...)`` default, and a
    ``Depends`` carried in an ``Annotated`` type alias such as
    ``AsyncSessionDep``.

    Args:
        endpoint: The handler function the application resolved to.

    Returns:
        The dependency callables declared on the signature.
    """
    providers: set[object] = set()
    for parameter in inspect.signature(endpoint).parameters.values():
        default = parameter.default
        if isinstance(default, _DEPENDS_TYPES):
            providers.add(default.dependency)
        for extra in getattr(parameter.annotation, "__metadata__", ()):
            if isinstance(extra, _DEPENDS_TYPES):
                providers.add(extra.dependency)
    return providers


async def _create_user_created_on(
    db_session: AsyncSession, email: str, day: date, hour: int = 12
) -> None:
    """Create a user whose ``created_at`` is pinned to ``day`` at ``hour``.

    Args:
        db_session: The session to create through.
        email: Unique email for the user.
        day: The calendar day the user should appear to have been created on.
        hour: Hour of that day to stamp (default noon).
    """
    user = await crud.create_user(
        db_session, UserCreate(email=email, full_name=email.split("@", 1)[0])
    )
    user.created_at = datetime(day.year, day.month, day.day, hour, 0, 0)
    await db_session.flush()


def _counts_by_day(response: Response) -> dict[date, int]:
    """Read a daily-count response body into ``{day: count}``.

    Args:
        response: A served ``GET /users/created-per-day`` response.

    Returns:
        The reported days and their counts.

    Raises:
        AssertionError: If the body is not the array of {date, count} the route
            documents, which is itself a failure worth reporting loudly.
    """
    body = response.json()
    assert isinstance(body, list), f"expected a JSON array, got {type(body).__name__}"
    entries: dict[date, int] = {}
    for entry in body:
        assert isinstance(entry, dict), f"expected an object entry, got {entry!r}"
        assert set(entry) == {"date", "count"}, f"unexpected entry shape: {entry!r}"
        entries[date.fromisoformat(str(entry["date"]))] = int(entry["count"])
    return entries


@pytest.fixture
def injected_db(db_session: AsyncSession) -> Iterator[InjectionLog]:
    """Point the application's DB-session dependencies at this test's session.

    Both provider identities are overridden, so the pin holds whether the handler
    asks for ``get_db`` (as the rest of the users router does) or for the
    ``AsyncSessionDep`` alias built on ``get_async_session``.

    Args:
        db_session: The per-test database session.

    Yields:
        The log of sessions handed out, and how often they were asked for.
    """
    log = InjectionLog()

    async def provider() -> AsyncIterator[AsyncSession]:
        log.sessions.append(db_session)
        yield db_session

    for provider_key in DB_SESSION_PROVIDERS:
        app.dependency_overrides[provider_key] = provider  # type: ignore[assignment]
    try:
        yield log
    finally:
        for provider_key in DB_SESSION_PROVIDERS:
            app.dependency_overrides.pop(provider_key, None)


class _SessionWhoseQueryFails:
    """A session that fails the way an unreachable database makes one fail."""

    async def execute(self, *_args: object) -> Any:
        """Raise the error a broken query raises.

        Args:
            *_args: The statement and parameters, ignored.

        Raises:
            SQLAlchemyError: Always.
        """
        raise SQLAlchemyError("the daily-count aggregate could not run")


@asynccontextmanager
async def _db_that_raises() -> AsyncIterator[None]:
    """Serve requests from a session whose queries fail.

    Yields:
        Nothing; the override is removed on exit.
    """

    async def provider() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, _SessionWhoseQueryFails())

    for provider_key in DB_SESSION_PROVIDERS:
        app.dependency_overrides[provider_key] = provider  # type: ignore[assignment]
    try:
        yield
    finally:
        for provider_key in DB_SESSION_PROVIDERS:
            app.dependency_overrides.pop(provider_key, None)


class TestRouteIsRegistered:
    """AC-001: the application answers GET /users/created-per-day."""

    async def test_the_path_is_on_the_application(self) -> None:
        """The route is on the app's own URL map, not only on a detached router."""
        path_item = app.openapi()["paths"].get(ENDPOINT_PATH)
        assert path_item is not None, (
            f"{ENDPOINT_PATH} is not in the application's OpenAPI paths, so it was "
            "never registered on the app the process serves"
        )
        assert "get" in path_item, f"no GET operation on {ENDPOINT_PATH}: {path_item}"

    async def test_get_is_answered_without_a_route_error(
        self, injected_db: InjectionLog
    ) -> None:
        """A GET on the path is served by an endpoint, not by a 404 or 405."""
        async with _probing_client() as (client, _scope):
            response = await _get(client)

        assert response.status_code == HTTPStatus.OK
        assert injected_db.calls == 1

    async def test_the_body_is_a_json_array_of_date_count_entries(
        self, injected_db: InjectionLog
    ) -> None:
        """The response is the array of {date, count} the feature specifies."""
        async with _probing_client() as (client, _scope):
            response = await _get(client)

        body = response.json()
        assert isinstance(body, list)
        for entry in body:
            assert isinstance(entry, dict)
            assert set(entry) == {"date", "count"}

    async def test_the_literal_path_is_not_taken_by_the_user_id_route(
        self, injected_db: InjectionLog
    ) -> None:
        """/users/created-per-day must not be read as a user id.

        ``GET /users/{user_id}`` is declared after this route, and answers an
        unparseable id with 400; a 400 body here would mean the parameterised
        route had moved in front of the literal one.
        """
        async with _probing_client() as (client, _scope):
            response = await _get(client)

        assert response.status_code != HTTPStatus.BAD_REQUEST, response.text
        assert isinstance(response.json(), list)

    async def test_only_get_is_registered_and_a_post_is_rejected(self) -> None:
        """The path documents GET alone, so non-GET methods are refused."""
        path_item = app.openapi()["paths"][ENDPOINT_PATH]
        assert set(path_item) == {"get"}

        async with _probing_client() as (client, _scope):
            response = await client.post(ENDPOINT_PATH)

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


class TestRouteServesTheWindow:
    """The route, not only the query, delivers the feature's seven-day window."""

    async def test_seven_days_come_back_oldest_first_ending_today(
        self, injected_db: InjectionLog, db_session: AsyncSession
    ) -> None:
        """Seven entries, oldest day first, today last, counts on the right days."""
        today = date.today()
        await _create_user_created_on(db_session, "today@example.com", today)
        await _create_user_created_on(
            db_session, "three-days-ago@example.com", today - timedelta(days=3)
        )

        async with _probing_client() as (client, _scope):
            response = await _get(client)

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        days = [date.fromisoformat(entry["date"]) for entry in body]
        assert days == [today - timedelta(days=offset) for offset in range(6, -1, -1)]
        counts = _counts_by_day(response)
        assert counts[today] == 1
        assert counts[today - timedelta(days=3)] == 1

    async def test_users_created_outside_the_window_are_not_reported(
        self, injected_db: InjectionLog, db_session: AsyncSession
    ) -> None:
        """The window's seven days are the whole report: nothing older leaks in."""
        today = date.today()
        await _create_user_created_on(db_session, "inside@example.com", today)
        await _create_user_created_on(
            db_session, "inside-2@example.com", today - timedelta(days=5)
        )
        await _create_user_created_on(
            db_session, "long-ago@example.com", today - timedelta(days=20)
        )

        async with _probing_client() as (client, _scope):
            response = await _get(client)

        counts = _counts_by_day(response)
        assert len(counts) == DEFAULT_WINDOW_DAYS
        assert sum(counts.values()) == 2

    async def test_a_quiet_database_still_answers_with_the_full_window(
        self, injected_db: InjectionLog
    ) -> None:
        """With nothing created in the window, the window is still reported whole."""
        today = date.today()

        async with _probing_client() as (client, _scope):
            response = await _get(client)

        counts = _counts_by_day(response)
        assert len(counts) == DEFAULT_WINDOW_DAYS
        assert all(count == 0 for count in counts.values())
        assert max(counts) == today and min(counts) == today - timedelta(days=6)


class TestSessionArrivesByInjection:
    """AC-002: the handler's session comes from dependency injection."""

    async def test_the_route_declares_a_db_session_dependency(
        self, injected_db: InjectionLog
    ) -> None:
        """The handler takes its session from FastAPI, holding none of its own."""
        async with _probing_client() as (client, scope):
            await _get(client)

        route = _route_of(scope)
        resolved: set[object] = set()
        _dependency_callables(route.dependant, resolved)
        declared = _providers_of(route.endpoint)
        assert declared, (
            f"{route.endpoint.__name__} declares no Depends() at all, so the "
            "database session cannot be arriving through dependency injection"
        )
        assert resolved & set(DB_SESSION_PROVIDERS), (
            "no DB-session provider of this application appears in the route's "
            f"dependency graph; it holds {sorted(str(c) for c in resolved)}"
        )

    async def test_the_response_reflects_rows_reached_through_the_injected_session(
        self, injected_db: InjectionLog, db_session: AsyncSession
    ) -> None:
        """The handler reads the session the app injected, not one it opened itself.

        The row is written on the test session and only ever reaches the handler if
        the handler was handed that session.
        """
        await _create_user_created_on(db_session, "injected@example.com", date.today())

        async with _probing_client() as (client, _scope):
            response = await _get(client)

        assert injected_db.calls == 1
        assert _counts_by_day(response)[date.today()] == 1

    def test_no_users_feature_file_builds_a_session_or_engine_itself(self) -> None:
        """ADR-006's prohibition, checked on this feature's whole module.

        Rule R-ADR006-1 scans all of ``src/``; this pins the part of it this task
        is responsible for, so a change elsewhere in the repository cannot make
        this test disagree with what ``src/users`` does.
        """
        offenders: list[str] = []
        for source in sorted(_USERS_SOURCE_ROOT.rglob("*.py")):
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func
                name: str | None = None
                if isinstance(function, ast.Name):
                    name = function.id
                elif isinstance(function, ast.Attribute):
                    name = function.attr
                if name in _FORBIDDEN_SESSION_CALLS:
                    offenders.append(f"{source.name}:{node.lineno} {name}()")

        assert offenders == [], (
            "a session or engine built in src/users is ADR-006's forbidden "
            f"pattern; take it from Depends instead: {offenders}"
        )


class TestDatabaseUnavailable:
    """The route's degradation when the database cannot answer."""

    async def test_a_failing_query_is_a_503_not_seven_quiet_zeros(self) -> None:
        """A database that never answered must not read as a week of zeroes."""
        async with _db_that_raises(), _probing_client() as (client, _scope):
            response = await _get(client)

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert "Database unavailable" in response.json()["detail"]
