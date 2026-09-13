"""Tests for the per-day user-creation counts, the CRUD half of the analytics.

Covers TASK-BD8F-002:

- AC-001: ``get_users_created_per_day`` answers with the number of users created
  on each of the last seven days.
- AC-002: those days come back oldest first.
- AC-004: the new analytics callable carries annotations on its arguments and
  on its return.

The counts are read from real rows through the database this suite settles (see
``tests/__init__.py``), not from a mock, so what these tests prove is that the
query and the day arithmetic agree with the rows on disk. Every test but the one
about the default window names its own last day, so none of them trusts the wall
clock for the window it asserts on.
"""

from __future__ import annotations

import inspect
from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.models import User
from src.users.schemas import DEFAULT_USER_CREATION_WINDOW_DAYS, UserCreationStats

# The last day of the window these tests ask for. Fixed on purpose: the rows it
# counts are written by the test itself, so the answer cannot drift with today.
WINDOW_END = date(2026, 7, 8)

# The seven-day window that ends on WINDOW_END, oldest day first.
WINDOW_START = WINDOW_END - timedelta(days=DEFAULT_USER_CREATION_WINDOW_DAYS - 1)


def timestamp_on(day: date, hour: int = 12) -> datetime:
    """Return a naive UTC timestamp on ``day``.

    Naive matches the ``created_at`` column, which carries no timezone; an aware
    timestamp against that column is what made the count-today query fail on
    PostgreSQL once already.

    Args:
        day: The calendar day to place the timestamp on.
        hour: Hour of day, defaulting to midday.

    Returns:
        datetime: The naive timestamp.
    """
    return datetime.combine(day, time(hour))


async def add_user_created_on(
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
    user = User(email=email, created_at=timestamp_on(day, hour))
    session.add(user)
    await session.commit()
    return user


def counts_by_day(stats: UserCreationStats) -> list[int]:
    """Return the per-day counts in the order the response carries them.

    Args:
        stats: The stats a CRUD call returned.

    Returns:
        list[int]: The counts, in the response's own order.
    """
    return [entry.count for entry in stats.days]


def days_of(stats: UserCreationStats) -> list[date]:
    """Return the days in the order the response carries them.

    Args:
        stats: The stats a CRUD call returned.

    Returns:
        list[date]: The days, in the response's own order.
    """
    return [entry.date for entry in stats.days]


class TestUsersCreatedPerDayCounts:
    """AC-001: correct counts for each of the last seven days."""

    async def test_an_empty_database_answers_with_seven_zero_days(
        self, db_session: AsyncSession
    ) -> None:
        """Nothing created is still seven days of data, each answering zero."""
        stats = await crud.get_users_created_per_day(db_session, end_day=WINDOW_END)

        assert isinstance(stats, UserCreationStats)
        assert len(stats.days) == DEFAULT_USER_CREATION_WINDOW_DAYS
        assert counts_by_day(stats) == [0] * DEFAULT_USER_CREATION_WINDOW_DAYS
        assert stats.total == 0

    async def test_each_day_carries_the_number_of_users_created_on_it(
        self, db_session: AsyncSession
    ) -> None:
        """Days with creations carry their own count, empty days carry zero."""
        await add_user_created_on(db_session, "first@example.com", WINDOW_START)
        await add_user_created_on(
            db_session, "second@example.com", WINDOW_START, hour=23
        )
        await add_user_created_on(
            db_session, "middle@example.com", WINDOW_START + timedelta(days=3)
        )
        for index in range(4):
            await add_user_created_on(
                db_session, f"latest-{index}@example.com", WINDOW_END
            )

        stats = await crud.get_users_created_per_day(db_session, end_day=WINDOW_END)

        assert counts_by_day(stats) == [2, 0, 0, 1, 0, 0, 4]
        assert stats.total == 7

    async def test_the_total_is_the_sum_of_the_days(
        self, db_session: AsyncSession
    ) -> None:
        """The window's total cannot disagree with the days it carries."""
        for index in range(3):
            await add_user_created_on(
                db_session, f"sum-{index}@example.com", WINDOW_START + timedelta(days=1)
            )

        stats = await crud.get_users_created_per_day(db_session, end_day=WINDOW_END)

        assert stats.total == sum(counts_by_day(stats))
        assert stats.total == 3

    async def test_creations_before_the_window_are_left_out(
        self, db_session: AsyncSession
    ) -> None:
        """A user created eight days ago belongs to an older window, not this one."""
        await add_user_created_on(
            db_session, "long-ago@example.com", WINDOW_START - timedelta(days=1)
        )
        await add_user_created_on(db_session, "recent@example.com", WINDOW_START)

        stats = await crud.get_users_created_per_day(db_session, end_day=WINDOW_END)

        assert stats.total == 1
        assert counts_by_day(stats) == [1, 0, 0, 0, 0, 0, 0]

    async def test_a_day_is_counted_whenever_in_the_day_it_fell(
        self, db_session: AsyncSession
    ) -> None:
        """Midnight and one second before midnight are the same creation day."""
        await add_user_created_on(db_session, "midnight@example.com", WINDOW_START, 0)
        await add_user_created_on(db_session, "late@example.com", WINDOW_START, hour=23)

        stats = await crud.get_users_created_per_day(db_session, end_day=WINDOW_END)

        assert counts_by_day(stats)[0] == 2

    async def test_soft_deleted_users_are_not_counted_as_creations(
        self, db_session: AsyncSession
    ) -> None:
        """A deleted user stops counting as a creation, as everywhere else."""
        kept = await add_user_created_on(db_session, "kept@example.com", WINDOW_END)
        removed = await add_user_created_on(
            db_session, "removed@example.com", WINDOW_END
        )
        removed.deleted_at = datetime.combine(WINDOW_END, time(18))
        await db_session.commit()

        stats = await crud.get_users_created_per_day(db_session, end_day=WINDOW_END)

        assert stats.total == 1
        assert counts_by_day(stats)[-1] == 1
        assert kept.email == "kept@example.com"

    async def test_the_default_window_answers_for_the_seven_days_ending_today(
        self, db_session: AsyncSession
    ) -> None:
        """With no day named, the caller gets the last seven days."""
        day_before = date.today()
        await add_user_created_on(
            db_session, "recent@example.com", day_before - timedelta(days=3)
        )

        stats = await crud.get_users_created_per_day(db_session)
        last_day = days_of(stats)[-1]

        assert len(stats.days) == DEFAULT_USER_CREATION_WINDOW_DAYS
        assert last_day in {day_before, date.today()}
        assert days_of(stats)[0] == last_day - timedelta(
            days=DEFAULT_USER_CREATION_WINDOW_DAYS - 1
        )
        assert stats.total == 1
        assert stats.days[-4].count == 1

    async def test_a_wider_window_can_be_asked_for(
        self, db_session: AsyncSession
    ) -> None:
        """The window size is a parameter; seven is only its default."""
        await add_user_created_on(
            db_session,
            "early@example.com",
            WINDOW_END - timedelta(days=9),
        )

        stats = await crud.get_users_created_per_day(
            db_session, end_day=WINDOW_END, window_days=10
        )

        assert len(stats.days) == 10
        assert stats.total == 1
        assert counts_by_day(stats)[0] == 1

    async def test_a_window_shorter_than_one_day_is_refused(
        self, db_session: AsyncSession
    ) -> None:
        """A window of no days is a programming error, said plainly."""
        with pytest.raises(ValueError, match="at least one"):
            await crud.get_users_created_per_day(
                db_session, end_day=WINDOW_END, window_days=0
            )


class TestUsersCreatedPerDayOrdering:
    """AC-002: the days come back oldest first."""

    async def test_days_run_oldest_first_whatever_order_rows_arrive_in(
        self, db_session: AsyncSession
    ) -> None:
        """Inserting newest first still answers oldest first."""
        for offset in range(DEFAULT_USER_CREATION_WINDOW_DAYS - 1, -1, -1):
            await add_user_created_on(
                db_session,
                f"offset-{offset}@example.com",
                WINDOW_END - timedelta(days=offset),
            )

        stats = await crud.get_users_created_per_day(db_session, end_day=WINDOW_END)

        assert days_of(stats) == [
            WINDOW_START + timedelta(days=offset)
            for offset in range(DEFAULT_USER_CREATION_WINDOW_DAYS)
        ]

    async def test_the_days_are_seven_consecutive_calendar_days(
        self, db_session: AsyncSession
    ) -> None:
        """No day is skipped and none repeats: one step per entry, oldest onward."""
        await add_user_created_on(db_session, "one@example.com", WINDOW_END)

        stats = await crud.get_users_created_per_day(db_session, end_day=WINDOW_END)

        assert days_of(stats) == sorted(days_of(stats))
        assert list(days_of(stats)) == list(dict.fromkeys(days_of(stats)))
        steps = {
            later - earlier
            for earlier, later in zip(days_of(stats), days_of(stats)[1:], strict=False)
        }
        assert steps == {timedelta(days=1)}


class TestUsersCreatedPerDayContract:
    """AC-004: the analytics callable says what it takes and what it returns."""

    def test_the_function_is_fully_annotated(self) -> None:
        """Every argument and the return carry an annotation."""
        signature = inspect.signature(crud.get_users_created_per_day)

        assert signature.return_annotation is not inspect.Signature.empty
        for name, parameter in signature.parameters.items():
            assert parameter.annotation is not inspect.Parameter.empty, name

    def test_the_function_is_async(self) -> None:
        """The query runs on the async session, as the rest of the CRUD does."""
        assert inspect.iscoroutinefunction(crud.get_users_created_per_day)

    def test_the_seven_day_default_is_the_one_the_schema_declares(self) -> None:
        """The window default comes from the schema constant, not a second literal."""
        signature = inspect.signature(crud.get_users_created_per_day)

        assert (
            signature.parameters["window_days"].default
            == DEFAULT_USER_CREATION_WINDOW_DAYS
        )
