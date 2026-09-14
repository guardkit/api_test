"""Tests for the daily user-creation count query (TASK-54E1-001).

These exercise the CRUD query behind ``GET /users/created-per-day``:
exactly seven data points, ordered oldest first, over a window that
includes the oldest day. The endpoint itself is delivered by
TASK-54E1-002 and is out of scope here.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.models import User


def _start_of(day: date) -> datetime:
    """Return midnight of ``day`` as a naive datetime.

    The User model stores ``created_at`` as a naive DateTime column, so the
    fixtures build timestamps the same way ``count_users_today`` does.
    """
    return datetime(day.year, day.month, day.day)


async def _seed_user(
    db: AsyncSession, email: str, created_at: datetime, *, deleted: bool = False
) -> User:
    """Insert a user whose ``created_at`` is pinned to ``created_at``.

    Args:
        db: The async database session.
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


def _dates(rows: list[dict[str, int | str]]) -> list[date]:
    """Extract the parsed ``date`` values from query rows."""
    return [date.fromisoformat(str(row["date"])) for row in rows]


def _counts(rows: list[dict[str, int | str]]) -> list[int]:
    """Extract the ``count`` values from query rows."""
    return [int(row["count"]) for row in rows]


class TestSevenDataPoints:
    """AC-001: the query returns exactly 7 data points for the last 7 days."""

    async def test_returns_exactly_seven_points_when_database_is_empty(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001: an empty database still yields seven zero-valued points."""
        rows = await crud.count_users_created_per_day(db_session)

        assert len(rows) == 7
        assert _counts(rows) == [0] * 7

    async def test_returns_exactly_seven_points_when_data_is_sparse(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001: users on only two days still yield seven points."""
        today = date.today()
        await _seed_user(db_session, "sparse-1@example.com", _start_of(today))
        await _seed_user(
            db_session,
            "sparse-2@example.com",
            _start_of(today - timedelta(days=3)) + timedelta(hours=9),
        )

        rows = await crud.count_users_created_per_day(db_session)

        assert len(rows) == 7
        assert sum(_counts(rows)) == 2

    async def test_seven_points_cover_today_back_to_six_days_ago(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001: the seven dates are today and the six days before it."""
        today = date.today()
        rows = await crud.count_users_created_per_day(db_session)

        assert _dates(rows) == [
            today - timedelta(days=offset) for offset in range(6, -1, -1)
        ]

    async def test_point_count_is_configurable(self, db_session: AsyncSession) -> None:
        """AC-001: the window size is a parameter, defaulting to seven days."""
        rows = await crud.count_users_created_per_day(db_session, days=3)

        assert len(rows) == 3
        assert _counts(rows) == [0] * 3

    async def test_invalid_window_raises_value_error(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001: a non-positive window is rejected rather than silently wrong."""
        with pytest.raises(ValueError, match="days must be >= 1"):
            await crud.count_users_created_per_day(db_session, days=0)


class TestOldestFirstOrdering:
    """AC-002: data points are ordered oldest first."""

    async def test_dates_ascend_from_oldest_to_most_recent(
        self, db_session: AsyncSession
    ) -> None:
        """AC-002: dates are strictly ascending, oldest day first."""
        rows = await crud.count_users_created_per_day(db_session)
        dates = _dates(rows)

        assert dates == sorted(dates)
        assert dates == sorted(set(dates))
        assert dates[0] == date.today() - timedelta(days=6)
        assert dates[-1] == date.today()

    async def test_counts_follow_their_dates_when_inserted_out_of_order(
        self, db_session: AsyncSession
    ) -> None:
        """AC-002: counts land on the right day even when inserted newest-first."""
        today = date.today()
        await _seed_user(
            db_session, "newest@example.com", _start_of(today) + timedelta(hours=12)
        )
        await _seed_user(
            db_session, "oldest@example.com", _start_of(today - timedelta(days=6))
        )
        await _seed_user(
            db_session, "mid-a@example.com", _start_of(today - timedelta(days=2))
        )
        await _seed_user(
            db_session, "mid-b@example.com", _start_of(today - timedelta(days=2))
        )

        rows = await crud.count_users_created_per_day(db_session)

        assert _counts(rows) == [1, 0, 0, 0, 2, 0, 1]


class TestInclusiveWindow:
    """AC-003: the 7-day window is inclusive of the oldest day."""

    async def test_user_on_oldest_day_of_window_is_counted(
        self, db_session: AsyncSession
    ) -> None:
        """AC-003: a user created at 00:00 on the oldest day is included."""
        oldest = date.today() - timedelta(days=6)
        await _seed_user(db_session, "oldest-day@example.com", _start_of(oldest))

        rows = await crud.count_users_created_per_day(db_session)

        assert _counts(rows)[0] == 1
        assert sum(_counts(rows)) == 1

    async def test_last_moment_of_oldest_day_is_counted(
        self, db_session: AsyncSession
    ) -> None:
        """AC-003: the whole oldest day is inside the window, not its first instant."""
        oldest = date.today() - timedelta(days=6)
        await _seed_user(
            db_session,
            "oldest-late@example.com",
            _start_of(oldest) + timedelta(hours=23, minutes=59, seconds=59),
        )

        rows = await crud.count_users_created_per_day(db_session)

        assert _counts(rows)[0] == 1

    async def test_day_before_window_is_excluded(
        self, db_session: AsyncSession
    ) -> None:
        """AC-003: the day before the oldest day falls outside the window."""
        too_old = date.today() - timedelta(days=7)
        await _seed_user(db_session, "too-old@example.com", _start_of(too_old))

        rows = await crud.count_users_created_per_day(db_session)

        assert _counts(rows) == [0] * 7

    async def test_today_is_included(self, db_session: AsyncSession) -> None:
        """AC-003: the most recent day of the window is included."""
        await _seed_user(
            db_session,
            "today@example.com",
            _start_of(date.today()) + timedelta(hours=12),
        )

        rows = await crud.count_users_created_per_day(db_session)

        assert _counts(rows)[-1] == 1


class TestWindowAggregationDetails:
    """Supporting behaviour of the query: per-day totals and soft-delete scope."""

    async def test_counts_per_day_are_accurate(self, db_session: AsyncSession) -> None:
        """Multiple users on the same day collapse into that day's single count."""
        today = date.today()
        for offset, expected in ((6, 1), (4, 3), (0, 2)):
            day = _start_of(today - timedelta(days=offset))
            for index in range(expected):
                await _seed_user(
                    db_session,
                    f"day{offset}-{index}@example.com",
                    day + timedelta(hours=index),
                )

        rows = await crud.count_users_created_per_day(db_session)

        assert _counts(rows) == [1, 0, 3, 0, 0, 0, 2]
        assert [row["date"] for row in rows] == [
            day.isoformat() for day in _dates(rows)
        ]

    async def test_soft_deleted_users_are_excluded(
        self, db_session: AsyncSession
    ) -> None:
        """Deleted users are out of scope, matching the other count queries."""
        today = date.today()
        await _seed_user(db_session, "live@example.com", _start_of(today))
        await _seed_user(
            db_session,
            "gone@example.com",
            _start_of(today - timedelta(days=1)),
            deleted=True,
        )

        rows = await crud.count_users_created_per_day(db_session)

        assert _counts(rows) == [0, 0, 0, 0, 0, 0, 1]

    async def test_rows_expose_date_string_and_integer_count(
        self, db_session: AsyncSession
    ) -> None:
        """Each data point is an ISO-8601 date plus an integer count."""
        rows = await crud.count_users_created_per_day(db_session)

        assert all(set(row) == {"date", "count"} for row in rows)
        assert all(isinstance(row["date"], str) for row in rows)
        assert all(isinstance(row["count"], int) for row in rows)
        assert all(
            isinstance(date.fromisoformat(str(row["date"])), date) for row in rows
        )


class TestDayNormalization:
    """Grouped-day values from any driver normalise to one calendar day.

    ``date(created_at)`` comes back as an ISO string on SQLite and as a
    native ``date`` on PostgreSQL. Anything else is a driver surprise and
    must raise instead of silently bucketing users onto the wrong day.
    """

    def test_datetime_normalises_to_its_calendar_day(self) -> None:
        """A timestamp maps onto the day it falls on."""
        assert crud._as_calendar_day(datetime(2026, 9, 14, 23, 59)) == date(2026, 9, 14)

    def test_date_passes_through_unchanged(self) -> None:
        """A native date is already the value the query needs."""
        assert crud._as_calendar_day(date(2026, 9, 14)) == date(2026, 9, 14)

    def test_iso_string_is_parsed(self) -> None:
        """SQLite's string form parses, with or without a time component."""
        assert crud._as_calendar_day("2026-09-14") == date(2026, 9, 14)
        assert crud._as_calendar_day("2026-09-14 23:59:59.000000") == date(2026, 9, 14)

    def test_unparseable_string_raises(self) -> None:
        """An unreadable day value is reported, not guessed at."""
        with pytest.raises(ValueError, match="not an ISO-8601 date"):
            crud._as_calendar_day("yesterday")

    def test_unsupported_type_raises(self) -> None:
        """A non-date value names the type it received."""
        with pytest.raises(ValueError, match="expected date or ISO string"):
            crud._as_calendar_day(1726300800)
