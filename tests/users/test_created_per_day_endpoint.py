"""The GET /users/created-per-day endpoint (TASK-A0AE-003).

The analytics behind this route already exists: ``crud.get_recent_daily_counts``
returns exactly seven zero-filled days, oldest first (TASK-A0AE-001/-002). What
this file pins is the HTTP surface over it:

* the route is wired and answers GET with 200 (AC-001),
* the body is the JSON the feature specifies — seven ``{date, count}`` data
  points, oldest day first, ISO8601 dates, integer counts (AC-002),
* a POST on that path is refused with 405 Method Not Allowed, because the path
  exists and carries no POST handler (AC-003).

The window is read from the live clock here, unlike the CRUD tests, which hand
their anchor in: the endpoint takes no anchor, so what it promises is that the
last data point is the day the request is served on. Every assertion is written
against that relative window, so the file says the same thing at 23:59 as at
00:01 — except across the instant a day turns over mid-request, which no test
written against a wall clock can avoid.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.main import app
from src.users import crud
from src.users.models import User

# The route under test and the length of the window it promises.
ENDPOINT = "/users/created-per-day"
WINDOW_DAYS = 7


def today() -> date:
    """Return the UTC day the endpoint measures its window from.

    Returns:
        The current calendar day in UTC, the newest day of the window.
    """
    return datetime.now(UTC).date()


def window_dates() -> list[date]:
    """Return the seven days of the window, oldest first.

    Returns:
        Seven consecutive days ending on the current UTC day.
    """
    anchor = today()
    return [
        anchor - timedelta(days=offset) for offset in range(WINDOW_DAYS - 1, -1, -1)
    ]


def at(day: date, hour: int = 12) -> datetime:
    """Return a naive timestamp on a given day, matching the column's type.

    ``users.created_at`` is a timestamp without time zone (alembic revision
    a143501c5e1f), so rows are written the way the column stores them.

    Args:
        day: The calendar day to place the timestamp on.
        hour: The hour of day to use.

    Returns:
        A naive datetime on that day.
    """
    return datetime(day.year, day.month, day.day, hour, 0, 0)


async def seed_user(
    db: AsyncSession,
    email: str,
    created_at: datetime,
    deleted_at: datetime | None = None,
) -> None:
    """Put one user in the database with a chosen creation time.

    Args:
        db: The session to write through.
        email: The address, unique across the test.
        created_at: The creation timestamp to store.
        deleted_at: A soft-delete timestamp, when the user is deleted.
    """
    db.add(
        User(
            email=email,
            domain=email.split("@")[-1],
            created_at=created_at,
            deleted_at=deleted_at,
        )
    )
    await db.flush()


class TestCreatedPerDayRoute:
    """The route exists, answers GET, and refuses everything else."""

    # AC-001: the endpoint is implemented and reachable.
    async def test_get_answers_200(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """A GET on the route is routed and succeeds."""
        response = await async_client.get(ENDPOINT)
        assert response.status_code == HTTPStatus.OK

    # AC-003: a POST is refused, not silently served or redirected.
    async def test_post_is_method_not_allowed(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """POST to the analytics path is rejected with 405."""
        response = await async_client.post(ENDPOINT, json={})
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    # AC-003: "only GET is supported" covers the other writable verbs too.
    async def test_other_methods_are_refused(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """PUT, PATCH and DELETE are refused rather than served.

        They are refused as 405, or as the 400/404 the ``/users/{user_id}``
        routes hand back when Starlette resolves the path to one of them: this
        path is one segment, so it is indistinguishable from a user id to those
        routes, and a whole-path match wins over the method-only match here.
        Same story as ``/users/count``, documented in test_count_errors.py.
        Either way nothing writes, which is what "only GET is supported" asks.
        """
        for method in ("put", "patch", "delete"):
            response = await getattr(async_client, method)(ENDPOINT)
            assert response.status_code in {
                HTTPStatus.METHOD_NOT_ALLOWED,
                HTTPStatus.BAD_REQUEST,
                HTTPStatus.NOT_FOUND,
            }, method

    # AC-001: the route is part of the documented API, GET only.
    async def test_openapi_documents_a_get_only(self) -> None:
        """The OpenAPI schema carries the path with a get and no post."""
        schema = app.openapi()
        assert ENDPOINT in schema["paths"]
        operations = schema["paths"][ENDPOINT]
        assert "get" in operations
        assert "post" not in operations


class TestCreatedPerDayResponseShape:
    """The body: seven ``{date, count}`` points, oldest day first."""

    # AC-002: an empty database still answers with the full window.
    async def test_empty_database_answers_with_seven_zero_points(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Nothing created this week is seven zeros, not an empty array."""
        response = await async_client.get(ENDPOINT)
        assert response.status_code == HTTPStatus.OK

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == WINDOW_DAYS
        assert [point["count"] for point in data] == [0] * WINDOW_DAYS

    # AC-002: every data point carries a date and a count of the right type.
    async def test_each_point_carries_an_iso_date_and_an_integer_count(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Each point is exactly ``{"date": "YYYY-MM-DD", "count": int}``."""
        response = await async_client.get(ENDPOINT)
        assert response.status_code == HTTPStatus.OK

        for point in response.json():
            assert sorted(point) == ["count", "date"]
            assert isinstance(point["date"], str)
            assert isinstance(point["count"], int)
            assert date.fromisoformat(point["date"]).isoformat() == point["date"]

    # AC-002: the series is the seven days ending today, oldest first.
    async def test_the_window_is_the_last_seven_days_oldest_first(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Dates are consecutive, oldest day first, current day last."""
        response = await async_client.get(ENDPOINT)
        assert response.status_code == HTTPStatus.OK

        dates = [point["date"] for point in response.json()]
        assert dates == [day.isoformat() for day in window_dates()]
        assert dates[-1] == today().isoformat()

    # AC-002: the counts are the creations on each day of the window.
    async def test_counts_reflect_the_creations_of_each_day(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Days carry their own creations; days outside the window are absent."""
        days = window_dates()
        await seed_user(db_session, "one-a@example.com", at(days[-1]))
        await seed_user(db_session, "one-b@example.com", at(days[-1], hour=23))
        await seed_user(db_session, "two-a@example.com", at(days[-2]))
        # Older than the window, and one soft-deleted inside it: neither counts.
        await seed_user(db_session, "old@example.com", at(days[0] - timedelta(days=3)))
        await seed_user(
            db_session,
            "gone@example.com",
            at(days[-3]),
            deleted_at=at(days[-3], hour=18),
        )

        response = await async_client.get(ENDPOINT)
        assert response.status_code == HTTPStatus.OK

        counts = {point["date"]: point["count"] for point in response.json()}
        assert counts == {day.isoformat(): 0 for day in days} | {
            days[-1].isoformat(): 2,
            days[-2].isoformat(): 1,
        }


class TestCreatedPerDayErrors:
    """A database that cannot answer is reported, not papered over."""

    # AC-002: a failure is a 503 with the reason, never a half-shaped body.
    async def test_database_failure_answers_503(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """A SQLAlchemyError from the aggregation becomes a 503."""
        with patch.object(crud, "get_recent_daily_counts") as count_daily:
            count_daily.side_effect = SQLAlchemyError("Database connection failed")

            response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert "Database unavailable" in response.json()["detail"]
