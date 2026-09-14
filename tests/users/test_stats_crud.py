"""CRUD tests for the daily user-creation counts (TASK-D49B-002).

These exercise ``src.users.stats.get_daily_user_counts`` directly — the query
layer only.  The route belongs to TASK-D49B-003, the endpoint handler to
TASK-D49B-004 and the endpoint tests to TASK-D49B-005 (which owns
``tests/users/test_stats.py``), so nothing here builds a FastAPI app or issues
an HTTP request, and no test in this file needs editing when those land.

Every expected date is derived from ``date.today()``, the same clock the query
reads, so the assertions hold whichever day the suite runs on.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import NoReturn, cast

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import DailyUserCount, UserCreate
from src.users.stats import (
    DEFAULT_WINDOW_DAYS,
    MAX_WINDOW_DAYS,
    get_daily_user_counts,
)


async def _create_user_created_on(
    db_session: AsyncSession, email: str, day: date, hour: int = 12
) -> str:
    """Create a user whose ``created_at`` is pinned to ``day`` at ``hour``.

    Args:
        db_session: The session to create through.
        email: Unique email for the user.
        day: The calendar day the user should appear to have been created on.
        hour: Hour of that day to stamp (default noon).

    Returns:
        The new user's id.
    """
    user = await crud.create_user(
        db_session, UserCreate(email=email, full_name=email.split("@", 1)[0])
    )
    user.created_at = datetime(day.year, day.month, day.day, hour, 0, 0)
    await db_session.flush()
    return user.id


def _days_of(entries: list[DailyUserCount]) -> list[date]:
    """Return just the dates of ``entries``, in the order they came back."""
    return [entry.date for entry in entries]


def _counts_of(entries: list[DailyUserCount]) -> list[int]:
    """Return just the counts of ``entries``, in the order they came back."""
    return [entry.count for entry in entries]


class TestDailyUserCountsWindow:
    """AC-001/AC-002: the query is a daily count over a window of exactly seven days."""

    async def test_returns_exactly_seven_entries_by_default(
        self, db_session: AsyncSession
    ) -> None:
        """The default window is seven days, so seven entries come back."""
        entries = await get_daily_user_counts(db_session)

        assert len(entries) == 7
        assert DEFAULT_WINDOW_DAYS == 7

    async def test_returns_daily_user_count_entries(
        self, db_session: AsyncSession
    ) -> None:
        """Each entry is the (date, count) schema TASK-D49B-001 published."""
        entries = await get_daily_user_counts(db_session)

        assert all(isinstance(entry, DailyUserCount) for entry in entries)

    async def test_window_is_the_seven_days_ending_today(
        self, db_session: AsyncSession
    ) -> None:
        """The window is today plus the six days before it, with no gaps."""
        today = date.today()

        entries = await get_daily_user_counts(db_session)

        assert _days_of(entries) == [
            today - timedelta(days=offset) for offset in range(6, -1, -1)
        ]

    async def test_current_day_is_included_even_though_incomplete(
        self, db_session: AsyncSession
    ) -> None:
        """An incomplete current day is still reported, as the last entry."""
        today = date.today()

        entries = await get_daily_user_counts(db_session)

        assert entries[-1].date == today

    async def test_no_day_is_repeated(self, db_session: AsyncSession) -> None:
        """One entry per day: the window holds seven distinct calendar days."""
        entries = await get_daily_user_counts(db_session)

        assert len(set(_days_of(entries))) == len(entries)

    @pytest.mark.parametrize("days", [1, 2, 3, 7, 14])
    async def test_a_requested_window_returns_that_many_days(
        self, db_session: AsyncSession, days: int
    ) -> None:
        """The window size is honoured: ``days`` entries, today last."""
        today = date.today()

        entries = await get_daily_user_counts(db_session, days=days)

        assert len(entries) == days
        assert _days_of(entries) == [
            today - timedelta(days=offset) for offset in range(days - 1, -1, -1)
        ]


class TestDailyUserCountsOrdering:
    """AC-003: the query returns its days ordered oldest to newest."""

    async def test_entries_are_ordered_oldest_first(
        self, db_session: AsyncSession
    ) -> None:
        """Dates strictly ascend from the first entry to the last."""
        entries = await get_daily_user_counts(db_session)

        dates = _days_of(entries)
        assert dates == sorted(dates)
        assert dates == sorted(set(dates)), "dates must strictly ascend"

    async def test_oldest_and_newest_days_are_the_window_ends(
        self, db_session: AsyncSession
    ) -> None:
        """First entry is six days back, last entry is today."""
        today = date.today()

        entries = await get_daily_user_counts(db_session)

        assert entries[0].date == today - timedelta(days=6)
        assert entries[-1].date == today

    async def test_ordering_holds_when_data_is_written_newest_first(
        self, db_session: AsyncSession
    ) -> None:
        """Insertion order is irrelevant: the output is still oldest first."""
        today = date.today()
        for offset, hour in ((0, 1), (3, 2), (6, 3)):
            await _create_user_created_on(
                db_session,
                f"insert-order-{offset}@example.com",
                today - timedelta(days=offset),
                hour=hour,
            )

        entries = await get_daily_user_counts(db_session)

        assert _days_of(entries) == sorted(_days_of(entries))
        assert _counts_of(entries) == [1, 0, 0, 1, 0, 0, 1]


class TestDailyUserCountsPerDay:
    """AC-001: the CRUD counts the users created on each day of the window."""

    async def test_counts_match_the_users_created_on_each_day(
        self, db_session: AsyncSession
    ) -> None:
        """Each day's entry carries that day's creation count."""
        today = date.today()
        for index in range(2):
            await _create_user_created_on(
                db_session, f"today-{index}@example.com", today
            )
        for index in range(3):
            await _create_user_created_on(
                db_session,
                f"four-days-ago-{index}@example.com",
                today - timedelta(days=4),
            )
        await _create_user_created_on(
            db_session, "six-days-ago@example.com", today - timedelta(days=6)
        )

        entries = await get_daily_user_counts(db_session)

        assert _counts_of(entries) == [1, 0, 3, 0, 0, 0, 2]

    async def test_day_without_users_is_reported_as_zero_not_omitted(
        self, db_session: AsyncSession
    ) -> None:
        """A quiet day inside the window is a zero-count entry, not a gap."""
        today = date.today()
        await _create_user_created_on(db_session, "quiet-day@example.com", today)

        entries = await get_daily_user_counts(db_session)

        assert _counts_of(entries) == [0, 0, 0, 0, 0, 0, 1]
        assert all(entry.count == 0 for entry in entries[:-1])

    async def test_both_bounds_of_a_day_are_counted(
        self, db_session: AsyncSession
    ) -> None:
        """00:00:00 and 23:59:59 of the same day both count on that day."""
        today = date.today()
        await _create_user_created_on(
            db_session, "day-start@example.com", today, hour=0
        )
        await _create_user_created_on(db_session, "day-end@example.com", today, hour=23)

        entries = await get_daily_user_counts(db_session)

        assert entries[-1].count == 2

    async def test_total_equals_the_users_inside_the_window(
        self, db_session: AsyncSession
    ) -> None:
        """The counts sum to the number of users created within the window."""
        today = date.today()
        for index, offset in enumerate((0, 1, 2, 2, 5)):
            await _create_user_created_on(
                db_session,
                f"in-window-{index}@example.com",
                today - timedelta(days=offset),
            )

        entries = await get_daily_user_counts(db_session)

        assert sum(_counts_of(entries)) == 5


class TestDailyUserCountsWindowEdges:
    """AC-002: nothing outside the seven-day window is reported."""

    async def test_users_older_than_the_window_are_excluded(
        self, db_session: AsyncSession
    ) -> None:
        """A user created eight days ago appears in no entry of the window."""
        today = date.today()
        await _create_user_created_on(
            db_session, "eight-days-ago@example.com", today - timedelta(days=8)
        )
        await _create_user_created_on(
            db_session, "seven-days-ago@example.com", today - timedelta(days=7)
        )

        entries = await get_daily_user_counts(db_session)

        assert sum(_counts_of(entries)) == 0

    async def test_first_day_of_the_window_is_included(
        self, db_session: AsyncSession
    ) -> None:
        """Six days back is inside the window and is counted in the first entry."""
        today = date.today()
        await _create_user_created_on(
            db_session, "six-days-back@example.com", today - timedelta(days=6)
        )

        entries = await get_daily_user_counts(db_session)

        assert entries[0].date == today - timedelta(days=6)
        assert entries[0].count == 1

    async def test_users_stamped_in_the_future_are_excluded(
        self, db_session: AsyncSession
    ) -> None:
        """A creation timestamp after today falls outside the window."""
        today = date.today()
        await _create_user_created_on(
            db_session, "tomorrow@example.com", today + timedelta(days=1)
        )

        entries = await get_daily_user_counts(db_session)

        assert sum(_counts_of(entries)) == 0


class TestDailyUserCountsEmptyDataset:
    """AC-004: an empty dataset is handled by returning the window with zeros."""

    async def test_empty_database_returns_seven_zero_counts(
        self, db_session: AsyncSession
    ) -> None:
        """With no users at all the answer is seven days, every count zero."""
        entries = await get_daily_user_counts(db_session)

        assert len(entries) == 7
        assert _counts_of(entries) == [0, 0, 0, 0, 0, 0, 0]
        assert all(entry.count == 0 for entry in entries)

    async def test_window_with_no_creations_returns_seven_zero_counts(
        self, db_session: AsyncSession
    ) -> None:
        """Users existing only outside the window also yield seven zero counts."""
        today = date.today()
        await _create_user_created_on(
            db_session, "long-ago@example.com", today - timedelta(days=30)
        )

        entries = await get_daily_user_counts(db_session)

        assert len(entries) == 7
        assert set(_counts_of(entries)) == {0}

    async def test_empty_result_is_not_an_empty_list(
        self, db_session: AsyncSession
    ) -> None:
        """The empty case returns days, not an empty sequence to serialise."""
        entries = await get_daily_user_counts(db_session)

        assert entries != []
        assert len(entries) == DEFAULT_WINDOW_DAYS


class TestDailyUserCountsDeletedUsers:
    """Soft-deleted users are excluded, as every other count in this package."""

    async def test_soft_deleted_users_are_not_counted(
        self, db_session: AsyncSession
    ) -> None:
        """A user created today then deleted leaves today's count at zero."""
        today = date.today()
        user_id = await _create_user_created_on(
            db_session, "deleted@example.com", today
        )

        deleted = await crud.delete_user(db_session, user_id)
        assert deleted is True

        entries = await get_daily_user_counts(db_session)

        assert sum(_counts_of(entries)) == 0


class TestDailyUserCountsWindowSizeValidation:
    """The window argument is validated before anything reaches the database."""

    @pytest.mark.parametrize("days", [0, -1, -7])
    async def test_a_window_below_one_day_is_refused(
        self, db_session: AsyncSession, days: int
    ) -> None:
        """Zero or negative days is a bad request, said as a ValueError."""
        with pytest.raises(ValueError, match="at least 1"):
            await get_daily_user_counts(db_session, days=days)

    async def test_an_unbounded_window_is_refused(
        self, db_session: AsyncSession
    ) -> None:
        """A window past the ceiling is refused rather than run against the table."""
        with pytest.raises(ValueError, match=str(MAX_WINDOW_DAYS)):
            await get_daily_user_counts(db_session, days=MAX_WINDOW_DAYS + 1)

    async def test_a_failure_leaves_the_session_usable(
        self, db_session: AsyncSession
    ) -> None:
        """Refusing a bad window does not poison the session."""
        with pytest.raises(ValueError):
            await get_daily_user_counts(db_session, days=0)

        entries = await get_daily_user_counts(db_session)

        assert len(entries) == DEFAULT_WINDOW_DAYS


class _SessionWhoseQueryFails:
    """A session that fails the way a database does, for the failure path."""

    async def execute(self, *args: object) -> NoReturn:
        """Raise the error a broken query raises.

        Args:
            *args: The statement and parameters, ignored.

        Raises:
            SQLAlchemyError: Always.
        """
        raise SQLAlchemyError("the daily-count aggregate could not run")


class TestDailyUserCountsDatabaseFailure:
    """A database failure is logged and raised, never reported as an empty week."""

    async def test_a_failing_query_is_raised_not_swallowed(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The error reaches the caller instead of becoming seven false zeros."""
        session = cast(AsyncSession, _SessionWhoseQueryFails())

        with (
            caplog.at_level(logging.ERROR, logger="src.users.stats"),
            pytest.raises(SQLAlchemyError, match="could not run"),
        ):
            await get_daily_user_counts(session)

    async def test_a_failing_query_is_logged_with_context(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The failure is logged, naming the window that failed."""
        session = cast(AsyncSession, _SessionWhoseQueryFails())

        with caplog.at_level(logging.ERROR, logger="src.users.stats"):
            with pytest.raises(SQLAlchemyError):
                await get_daily_user_counts(session, days=7)

        messages = [record.getMessage() for record in caplog.records]
        assert any("7-day window" in message for message in messages)
