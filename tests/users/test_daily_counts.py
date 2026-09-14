"""Endpoint tests for ``GET /users/created-per-day`` (TASK-54E1-003).

The SQL query behind this endpoint is already pinned by
``tests/users/test_created_per_day_counts.py`` (TASK-54E1-001). What is pinned
here is the endpoint's own HTTP contract, one class per acceptance criterion:

* AC-001 — exactly seven data points per response
* AC-002 — ordered from the oldest day to the most recent day
* AC-003 — the seven-day window is inclusive of the oldest day and of today,
  and stops before the day before it
* AC-004 — every method other than GET is refused

Two pieces of this feature's behaviour are deliberately NOT pinned here,
because another task in FEAT-54E1 owns them: the 503 response when the
database is unavailable (TASK-54E1-004, ``src/users/router.py``
``get_created_per_day``) and the published documentation of the endpoint
(TASK-54E1-005, ``docs/``).

These tests read no environment variables, so their outcome depends only on
the code: which database the run talks to is settled once for the whole suite
in ``tests/__init__.py`` and handed to the test through the ``db_session`` and
``override_get_db`` fixtures in ``tests/conftest.py``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.models import User

ENDPOINT = "/users/created-per-day"

WINDOW_DAYS = 7


def _midnight(day: date) -> datetime:
    """Return midnight of ``day`` as a naive datetime.

    ``User.created_at`` is stored as a naive timestamp and the query builds its
    window from naive datetimes, so fixtures do the same.

    Args:
        day: The calendar day to place at midnight.

    Returns:
        datetime: Midnight of that day, no tzinfo.
    """
    return datetime(day.year, day.month, day.day)


def _end_of(day: date) -> datetime:
    """Return the last whole second of ``day`` as a naive datetime.

    Args:
        day: The calendar day to place at its final second.

    Returns:
        datetime: 23:59:59 of that day, no tzinfo.
    """
    return _midnight(day) + timedelta(hours=23, minutes=59, seconds=59)


async def _seed_user(
    db: AsyncSession,
    email: str,
    created_at: datetime,
    *,
    deleted: bool = False,
) -> User:
    """Insert a user whose ``created_at`` is pinned to ``created_at``.

    Args:
        db: The async database session the endpoint will read from.
        email: Unique email for the user.
        created_at: Timestamp to store in ``created_at``.
        deleted: When True, the user is also soft-deleted.

    Returns:
        User: The persisted user.
    """
    user = User(
        email=email,
        full_name=email.split("@", 1)[0],
        domain=email.split("@", 1)[1],
        is_active=not deleted,
        created_at=created_at,
        deleted_at=created_at if deleted else None,
    )
    db.add(user)
    await db.flush()
    return user


def _days(body: list[dict[str, object]]) -> list[date]:
    """Return the calendar days of a response body, oldest first as sent.

    Args:
        body: The decoded JSON array of ``{date, count}`` objects.

    Returns:
        list[date]: The parsed days, in the order the response put them.
    """
    return [date.fromisoformat(str(point["date"])) for point in body]


def _counts(body: list[dict[str, object]]) -> list[int]:
    """Return the counts of a response body, in the order the response sent.

    Args:
        body: The decoded JSON array of ``{date, count}`` objects.

    Returns:
        list[int]: The counts, oldest day first.
    """
    return [int(str(point["count"])) for point in body]


def _window() -> list[date]:
    """Return the seven calendar days the endpoint must report, oldest first.

    Returns:
        list[date]: Today and the six days before it, oldest first.
    """
    today = date.today()
    return [today - timedelta(days=offset) for offset in range(WINDOW_DAYS - 1, -1, -1)]


async def _get_body(
    async_client: AsyncClient,
) -> list[dict[str, object]]:
    """Request the endpoint and return its decoded JSON array.

    Args:
        async_client: The ASGI-transport client.

    Returns:
        list[dict[str, object]]: The decoded array of data points.
    """
    response = await async_client.get(ENDPOINT)

    assert response.status_code == HTTPStatus.OK
    body: list[dict[str, object]] = response.json()
    return body


class TestSevenDataPoints:
    """AC-001: the endpoint returns exactly seven data points."""

    async def test_empty_database_still_returns_seven_data_points(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-001: with nothing to count the response is seven zeroed points."""
        body = await _get_body(async_client)

        assert len(body) == WINDOW_DAYS
        assert _counts(body) == [0] * WINDOW_DAYS

    async def test_every_data_point_is_a_date_and_a_count(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-001: each of the seven points carries exactly date and count."""
        body = await _get_body(async_client)

        assert len(body) == WINDOW_DAYS
        assert all(set(point) == {"date", "count"} for point in body)
        assert all(
            isinstance(date.fromisoformat(str(point["date"])), date) for point in body
        )
        assert all(isinstance(point["count"], int) for point in body)

    async def test_sparse_data_still_returns_seven_data_points(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-001: users on two days only still yield seven points."""
        today = date.today()
        await _seed_user(db_session, "sparse-a@example.com", _midnight(today))
        await _seed_user(
            db_session,
            "sparse-b@example.com",
            _midnight(today - timedelta(days=4)) + timedelta(hours=9),
        )

        body = await _get_body(async_client)

        assert len(body) == WINDOW_DAYS
        assert sum(_counts(body)) == 2

    async def test_seven_points_cover_today_and_the_six_days_before_it(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-001: the seven days reported are today and the six before it."""
        body = await _get_body(async_client)

        assert _days(body) == _window()


class TestOldestToNewestOrdering:
    """AC-002: the data points are ordered oldest day first, today last."""

    async def test_days_ascend_strictly_from_oldest_to_today(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-002: days strictly ascend, oldest day of the window first."""
        body = await _get_body(async_client)
        days = _days(body)

        assert days == sorted(days)
        assert len(set(days)) == len(days)
        assert days[0] == date.today() - timedelta(days=WINDOW_DAYS - 1)
        assert days[-1] == date.today()

    async def test_counts_stay_on_their_own_day_when_rows_written_newest_first(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-002: order comes from the days, not from the insertion order.

        The users are written newest-first on purpose: a response ordered by
        insertion would come out backwards here.
        """
        today = date.today()
        await _seed_user(
            db_session, "newest@example.com", _midnight(today) + timedelta(hours=12)
        )
        for index in range(2):
            await _seed_user(
                db_session,
                f"middle-{index}@example.com",
                _midnight(today - timedelta(days=2)),
            )
        await _seed_user(
            db_session, "oldest@example.com", _midnight(today - timedelta(days=6))
        )

        body = await _get_body(async_client)

        assert _counts(body) == [1, 0, 0, 0, 2, 0, 1]
        paired = dict(zip(_days(body), _counts(body), strict=True))
        assert paired[today - timedelta(days=6)] == 1
        assert paired[today - timedelta(days=2)] == 2
        assert paired[today] == 1

    async def test_newest_point_is_the_most_recent_day(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-002: the last point of the array is always today."""
        body = await _get_body(async_client)

        assert _days(body)[-1] == date.today()
        assert (_days(body)[-1] - _days(body)[0]).days == WINDOW_DAYS - 1


class TestSevenDayWindowInclusivity:
    """AC-003: the seven-day window includes the oldest day, and stops there."""

    async def test_oldest_day_of_the_window_is_reported(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-003: the first data point names the oldest day of the window."""
        body = await _get_body(async_client)

        assert _days(body)[0] == date.today() - timedelta(days=WINDOW_DAYS - 1)

    async def test_user_at_the_start_of_the_oldest_day_is_counted(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-003: midnight on the oldest day is inside the window."""
        oldest = date.today() - timedelta(days=WINDOW_DAYS - 1)
        await _seed_user(db_session, "oldest-start@example.com", _midnight(oldest))

        body = await _get_body(async_client)

        assert _counts(body)[0] == 1
        assert sum(_counts(body)) == 1

    async def test_user_at_the_end_of_the_oldest_day_is_counted(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-003: the whole oldest day is inside the window, not an instant."""
        oldest = date.today() - timedelta(days=WINDOW_DAYS - 1)
        await _seed_user(db_session, "oldest-end@example.com", _end_of(oldest))

        body = await _get_body(async_client)

        assert _counts(body)[0] == 1
        assert sum(_counts(body)) == 1

    async def test_today_is_counted_as_the_most_recent_day(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-003: the most recent day of the window is inside it."""
        await _seed_user(db_session, "today@example.com", _midnight(date.today()))

        body = await _get_body(async_client)

        assert _days(body)[-1] == date.today()
        assert _counts(body)[-1] == 1
        assert sum(_counts(body)) == 1

    async def test_day_before_the_window_is_excluded(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-003: a day outside the window is neither counted nor reported."""
        too_old = date.today() - timedelta(days=WINDOW_DAYS)
        await _seed_user(db_session, "too-old@example.com", _end_of(too_old))

        body = await _get_body(async_client)

        assert _days(body) == _window()
        assert too_old not in _days(body)
        assert _counts(body) == [0] * WINDOW_DAYS


class TestNonGetRejection:
    """AC-004: the endpoint refuses every method that is not GET.

    POST, PUT, PATCH and DELETE are the methods ``src/users/router.py``
    registers explicitly for this path. OPTIONS is left alone: a future CORS
    configuration legitimately answers it, so pinning it here would pin a
    decision that belongs to no task in this feature.
    """

    @pytest.mark.parametrize(
        ("method", "method_name"),
        [
            ("POST", "post"),
            ("PUT", "put"),
            ("PATCH", "patch"),
            ("DELETE", "delete"),
        ],
    )
    async def test_non_get_methods_are_refused(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        method: str,
        method_name: str,
    ) -> None:
        """AC-004: a non-GET request is rejected as method-not-allowed.

        The refusal must name GET as the only method this path serves. A
        response that fell through to another route (for example
        ``/users/{user_id}``) would either answer with a different status or
        advertise a wider set of methods, so this pins the dedicated rejection
        rather than an accidental 405.
        """
        response = await async_client.request(method_name, ENDPOINT)

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED, method
        allowed = {
            token.strip()
            for token in response.headers.get("allow", "").split(",")
            if token.strip()
        }
        assert allowed == {"GET"}

    async def test_a_refused_post_creates_no_user(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-004: the refusal is real, the endpoint has no write side effect."""
        refused = await async_client.post(
            ENDPOINT,
            json={"email": "not-created@example.com", "full_name": "Not Created"},
        )

        assert refused.status_code == HTTPStatus.METHOD_NOT_ALLOWED

        body = await _get_body(async_client)

        assert _counts(body) == [0] * WINDOW_DAYS

    async def test_get_on_the_same_path_is_still_served(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-004: the rejection route does not shadow the GET route."""
        body = await _get_body(async_client)

        assert len(body) == WINDOW_DAYS
