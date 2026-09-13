"""Tests for the GET /users/created-per-day analytics endpoint.

Covers TASK-BD8F-003 (the analytics router):

- AC-001: the endpoint answers with seven consecutive days, oldest day first,
  each day a ``{date, count}`` pair, plus the total those days account for, and
  it answers zero — not nothing — for a day without creations.
- AC-002: it requires authentication; an unauthenticated request is rejected.
- AC-004: the handler and the day-arithmetic helper it uses carry annotations on
  their arguments and on their return.

The counts are read from real rows through the database this suite settles (see
``tests/__init__.py``), never from a mock, so what these tests prove holds of the
query and the route wiring rather than of a stand-in.

Two clocks are in play, deliberately. Most tests pin the day the endpoint
believes is today (``frozen_today``), so their seeded rows and their expected
window cannot drift under them; the window-boundary tests leave the clock alone
and assert against the real calendar, which is the only way to prove the endpoint
reads the window from today rather than from a date baked into it.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from datetime import date, datetime, time, timedelta
from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.main import app
from src.users import router as router_module
from src.users.calculations import recent_creation_window_end
from src.users.models import User
from src.users.router import analytics_router, get_users_created_per_day
from src.users.schemas import DEFAULT_USER_CREATION_WINDOW_DAYS, UserCreationStats

AUTH_TOKEN = "dev-token"
AUTH_HEADERS = {"X-Auth-Token": AUTH_TOKEN}

URL = "/users/created-per-day"

# The last day of the window for the clock-pinned tests. Fixed on purpose: the
# rows are written by the test itself, so neither the window nor its counts can
# drift with the wall clock.
WINDOW_END = date(2026, 7, 8)
WINDOW_START = WINDOW_END - timedelta(days=DEFAULT_USER_CREATION_WINDOW_DAYS - 1)


async def seed_user_created_on(
    session: AsyncSession,
    email: str,
    day: date,
    hour: int = 12,
) -> User:
    """Persist one user whose creation timestamp falls on ``day``.

    Args:
        session: The session the test is working through.
        email: Address for the user; must be unique across the test.
        day: The calendar day the user was created on.
        hour: Hour of day, defaulting to midday.

    Returns:
        User: The persisted user.
    """
    user = User(email=email, created_at=datetime.combine(day, time(hour)))
    session.add(user)
    await session.commit()
    return user


def window_days(end: date) -> list[date]:
    """Return the days of the window ending on ``end``, oldest day first.

    Args:
        end: The newest day of the window.

    Returns:
        list[date]: The consecutive days of the window.
    """
    return [
        end - timedelta(days=offset)
        for offset in range(DEFAULT_USER_CREATION_WINDOW_DAYS - 1, -1, -1)
    ]


def response_days(body: dict[str, object]) -> list[str]:
    """Return the ISO days of a response body, in the order it carries them.

    Args:
        body: The decoded JSON body of a successful request.

    Returns:
        list[str]: The day strings, oldest first as sent.
    """
    days = body["days"]
    assert isinstance(days, list)
    return [str(entry["date"]) for entry in days if isinstance(entry, dict)]


def response_counts(body: dict[str, object]) -> list[int]:
    """Return the per-day counts of a response body, in the order it carries them.

    Args:
        body: The decoded JSON body of a successful request.

    Returns:
        list[int]: The counts, oldest day first as sent.
    """
    days = body["days"]
    assert isinstance(days, list)
    return [int(entry["count"]) for entry in days if isinstance(entry, dict)]


@pytest.fixture
def frozen_today(monkeypatch: pytest.MonkeyPatch) -> Iterator[date]:
    """Pin the day the endpoint counts from, so its window cannot drift.

    Only the day is pinned: the route, the CRUD call, the query and the response
    model all still run for real.

    Yields:
        date: The day the endpoint is made to believe is today.
    """
    today = WINDOW_END + timedelta(days=1)
    monkeypatch.setattr(
        router_module,
        "recent_creation_window_end",
        lambda: recent_creation_window_end(today),
    )
    yield today


class TestCreatedPerDayResponseShape:
    """AC-001: the response shape, seven days, oldest day first."""

    async def test_answers_with_exactly_seven_days(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
        frozen_today: date,
    ) -> None:
        """Seven days of data come back, and each is a date-and-count pair."""
        response = await async_client.get(URL, headers=AUTH_HEADERS)

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert isinstance(body, dict)
        assert len(body["days"]) == DEFAULT_USER_CREATION_WINDOW_DAYS == 7
        for entry in body["days"]:
            assert set(entry) == {"date", "count"}
            assert isinstance(entry["count"], int)
            assert entry["count"] >= 0

    async def test_days_run_from_the_oldest_to_the_newest(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
        frozen_today: date,
    ) -> None:
        """The days arrive oldest first, and they are one unbroken run."""
        response = await async_client.get(URL, headers=AUTH_HEADERS)

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert response_days(body) == [
            day.isoformat() for day in window_days(WINDOW_END)
        ]

        days = [date.fromisoformat(day) for day in response_days(body)]
        assert len(days) == DEFAULT_USER_CREATION_WINDOW_DAYS
        assert days == sorted(days)
        steps = [later - earlier for earlier, later in zip(days, days[1:])]
        assert all(step == timedelta(days=1) for step in steps)

    async def test_total_is_the_sum_of_the_days(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
        frozen_today: date,
    ) -> None:
        """The total agrees with the days it claims to summarise."""
        for offset, day in enumerate(window_days(WINDOW_END)[:3]):
            await seed_user_created_on(db_session, f"sum-{offset}@example.com", day)

        response = await async_client.get(URL, headers=AUTH_HEADERS)

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["total"] == sum(response_counts(body))
        assert body["total"] == 3

    async def test_empty_table_answers_seven_zero_days(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
        frozen_today: date,
    ) -> None:
        """An empty user table is still seven days of data, each answering zero."""
        response = await async_client.get(URL, headers=AUTH_HEADERS)

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert len(body["days"]) == DEFAULT_USER_CREATION_WINDOW_DAYS
        assert response_counts(body) == [0] * DEFAULT_USER_CREATION_WINDOW_DAYS
        assert body["total"] == 0

    async def test_every_day_of_the_window_is_answered_for(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
        frozen_today: date,
    ) -> None:
        """A day without creations carries a zero rather than going missing."""
        await seed_user_created_on(db_session, "first@example.com", WINDOW_START)
        await seed_user_created_on(db_session, "last@example.com", WINDOW_END)
        await seed_user_created_on(db_session, "last-b@example.com", WINDOW_END)

        response = await async_client.get(URL, headers=AUTH_HEADERS)

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        expected = [0] * DEFAULT_USER_CREATION_WINDOW_DAYS
        expected[0] = 1
        expected[-1] = 2
        assert response_days(body) == [
            day.isoformat() for day in window_days(WINDOW_END)
        ]
        assert response_counts(body) == expected
        assert body["total"] == 3

    async def test_only_the_window_is_counted(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
        frozen_today: date,
    ) -> None:
        """Creations before the window, or after it, do not reach the response."""
        await seed_user_created_on(
            db_session, "long-ago@example.com", WINDOW_START - timedelta(days=1)
        )
        await seed_user_created_on(
            db_session, "ahead@example.com", WINDOW_END + timedelta(days=1)
        )

        response = await async_client.get(URL, headers=AUTH_HEADERS)

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert response_counts(body) == [0] * DEFAULT_USER_CREATION_WINDOW_DAYS
        assert body["total"] == 0


class TestCreatedPerDayWindowBoundaries:
    """AC-001 boundaries: the window is the seven whole days before today."""

    async def test_the_oldest_day_is_seven_days_ago(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """The window opens exactly seven days before today."""
        response = await async_client.get(URL, headers=AUTH_HEADERS)

        assert response.status_code == HTTPStatus.OK
        oldest = date.fromisoformat(response_days(response.json())[0])
        assert oldest == date.today() - timedelta(
            days=DEFAULT_USER_CREATION_WINDOW_DAYS
        )

    async def test_the_newest_day_is_yesterday(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """The window closes yesterday: today is still in progress."""
        response = await async_client.get(URL, headers=AUTH_HEADERS)

        assert response.status_code == HTTPStatus.OK
        days = [date.fromisoformat(day) for day in response_days(response.json())]
        assert days[-1] == date.today() - timedelta(days=1)
        assert date.today() not in days

    async def test_a_user_created_today_is_not_counted(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """A creation dated today answers zero on every day of the response."""
        await seed_user_created_on(db_session, "today@example.com", date.today())

        response = await async_client.get(URL, headers=AUTH_HEADERS)

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert response_counts(body) == [0] * DEFAULT_USER_CREATION_WINDOW_DAYS
        assert body["total"] == 0


class TestCreatedPerDayAuthentication:
    """AC-002: the endpoint requires authentication."""

    async def test_a_request_without_a_token_is_rejected(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """No X-Auth-Token header means no analytics."""
        response = await async_client.get(URL)

        assert response.status_code == HTTPStatus.FORBIDDEN

    async def test_a_request_with_a_wrong_token_is_rejected(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """A token that is not the configured one means no analytics."""
        response = await async_client.get(
            URL, headers={"X-Auth-Token": "not-the-token"}
        )

        assert response.status_code == HTTPStatus.FORBIDDEN

    async def test_an_empty_token_is_rejected(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """An empty token is no token."""
        response = await async_client.get(URL, headers={"X-Auth-Token": ""})

        assert response.status_code == HTTPStatus.FORBIDDEN

    async def test_the_rejection_says_what_it_wants(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """The rejection names the token it needs, so a caller can fix it."""
        response = await async_client.get(URL)

        assert "token" in str(response.json()["detail"]).lower()

    async def test_an_authenticated_request_is_answered(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
        frozen_today: date,
    ) -> None:
        """The configured token is what the endpoint asks for, and is enough."""
        response = await async_client.get(URL, headers=AUTH_HEADERS)

        assert response.status_code == HTTPStatus.OK
        assert "days" in response.json()

    async def test_authentication_is_checked_before_the_database_is_read(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An unauthenticated request never reaches the counting query."""
        calls: list[str] = []

        async def spy(*args: object, **kwargs: object) -> UserCreationStats:
            calls.append("counted")
            return UserCreationStats(days=[])

        monkeypatch.setattr(router_module.crud, "get_users_created_per_day", spy)

        response = await async_client.get(URL)

        assert response.status_code == HTTPStatus.FORBIDDEN
        assert calls == []


class TestCreatedPerDayMethodContract:
    """The endpoint is read-only: a write method never returns the analytics."""

    async def test_a_post_request_is_rejected(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Nothing is created here, so POST is not allowed at all."""
        response = await async_client.post(URL, headers=AUTH_HEADERS)

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    @pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
    async def test_no_write_method_returns_the_analytics(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
        frozen_today: date,
        method: str,
    ) -> None:
        """No write method gets a 200, so none gets a body of days either."""
        response = await getattr(async_client, method)(URL, headers=AUTH_HEADERS)

        assert response.status_code != HTTPStatus.OK


class TestCreatedPerDayRouting:
    """The literal path wins, and the id route it sits beside still works."""

    async def test_the_path_is_not_read_as_a_user_id(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
        frozen_today: date,
    ) -> None:
        """/users/created-per-day is an analytics path, not a malformed user id."""
        response = await async_client.get(URL, headers=AUTH_HEADERS)

        assert response.status_code == HTTPStatus.OK
        assert "days" in response.json()

    async def test_a_user_id_lookup_still_works_beside_it(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Adding the analytics route did not take the id route out of service."""
        user = await seed_user_created_on(
            db_session, "lookup@example.com", date.today()
        )

        response = await async_client.get(f"/users/{user.id}")

        assert response.status_code == HTTPStatus.OK
        assert response.json()["email"] == "lookup@example.com"

    def test_the_route_is_declared_on_its_own_router(self) -> None:
        """The analytics path is carried by the analytics router."""
        paths = {
            (tuple(sorted(route.methods)), route.path)
            for route in analytics_router.routes
            if hasattr(route, "methods")
        }

        assert (("GET",), "/users/created-per-day") in paths

    def test_the_route_is_documented_with_openapi_tags(self) -> None:
        """The endpoint carries its tags and its failure codes in the schema."""
        schema = app.openapi()
        operation = schema["paths"][URL]["get"]

        assert "analytics" in operation["tags"]
        assert "users" in operation["tags"]
        assert "403" in operation["responses"]
        assert "application/json" in operation["responses"]["200"]["content"]
        described = {tag["name"] for tag in schema["tags"]}
        assert "analytics" in described


class TestCreatedPerDayAnnotations:
    """AC-004: the new code says what it takes and what it returns."""

    def test_the_handler_is_annotated(self) -> None:
        """Every argument and the return of the handler carry annotations."""
        signature = inspect.signature(get_users_created_per_day)

        assert inspect.iscoroutinefunction(get_users_created_per_day)
        assert signature.return_annotation is not inspect.Parameter.empty
        for name, parameter in signature.parameters.items():
            assert parameter.annotation is not inspect.Parameter.empty, name

    def test_the_window_helper_is_annotated(self) -> None:
        """The day-arithmetic helper carries its annotations too."""
        signature = inspect.signature(recent_creation_window_end)

        assert signature.return_annotation is not inspect.Parameter.empty
        for name, parameter in signature.parameters.items():
            assert parameter.annotation is not inspect.Parameter.empty, name

    def test_the_window_helper_answers_the_day_before_today(self) -> None:
        """The helper's one job: the window ends the day before the day it reads."""
        assert recent_creation_window_end(date(2026, 7, 9)) == date(2026, 7, 8)
