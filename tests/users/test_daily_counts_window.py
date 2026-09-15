"""The seven-day window over the daily user-creation counts (TASK-A0AE-002).

TASK-A0AE-001 put the aggregation in place — one row per calendar day that has
creations — and said plainly that choosing the window and filling the gaps
belonged to the task after it. This file pins that window:

* exactly seven data points come back, whatever the database holds (AC-001),
* oldest day first, newest day last (AC-002),
* a day nobody registered on reads as a count of zero, so an empty database
  still answers with seven days of zeros (AC-003),
* the current day is the last point of the window and carries only the
  creations that have happened so far, which is all a day that is still under
  way can carry (AC-004).

The window is measured from a day handed to the function rather than from
whatever today happens to be, so these checks say the same thing at 23:59 as
they do at 00:01. The one check that does read the real clock is the one that
pins the default window: seven days, ending today.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.models import User
from src.users.schemas import DailyCount

# The day the window is measured from, fixed so the run says the same thing
# whatever today is, and the first of the seven days that sit behind it.
ANCHOR = date(2026, 1, 11)
WINDOW_DAYS = 7
WINDOW_START = ANCHOR - timedelta(days=WINDOW_DAYS - 1)


def window_dates() -> list[date]:
    """Return the seven days of the window, oldest first.

    Returns:
        The seven consecutive days ending on ``ANCHOR``.
    """
    return [WINDOW_START + timedelta(days=step) for step in range(WINDOW_DAYS)]


def _at(day: date, hour: int = 12) -> datetime:
    """Return a naive timestamp on a given day, matching the column's type.

    ``users.created_at`` is a timestamp without time zone (alembic revision
    a143501c5e1f), so the rows are written the way the column stores them.

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


class TestSevenDayWindow:
    """The window itself: how many days, which days, and what each day says."""

    async def test_an_empty_database_answers_with_seven_days_of_zeros(
        self, db_session: AsyncSession
    ) -> None:
        """No creations is not an empty answer: seven days still come back."""
        counts = await crud.get_recent_daily_counts(db_session, today=ANCHOR)

        assert [item.model_dump() for item in counts] == [
            {"date": day.isoformat(), "count": 0} for day in window_dates()
        ]

    @pytest.mark.parametrize(
        "seeded_days",
        [[], [0], [0, 3], [0, 1, 2, 3, 4, 5, 6], [6]],
    )
    async def test_exactly_seven_days_come_back_whatever_the_database_holds(
        self, db_session: AsyncSession, seeded_days: list[int]
    ) -> None:
        """The window is the contract, not the number of days with rows.

        Args:
            db_session: The test's database session.
            seeded_days: Which days of the window to put creations on.
        """
        for step in seeded_days:
            await seed_user(
                db_session,
                f"user-{step}@window.test",
                _at(WINDOW_START + timedelta(days=step)),
            )

        counts = await crud.get_recent_daily_counts(db_session, today=ANCHOR)

        assert len(counts) == WINDOW_DAYS
        assert [item.date for item in counts] == [
            day.isoformat() for day in window_dates()
        ]

    async def test_days_come_back_oldest_to_newest_whatever_the_insert_order(
        self, db_session: AsyncSession
    ) -> None:
        """Ordering belongs to the window, not to the order rows were written.

        The newest day of the window is written first, the oldest last, so an
        answer that leaned on the database's own row order would come out
        backwards here.
        """
        await seed_user(db_session, "newest@order.test", _at(ANCHOR))
        await seed_user(
            db_session, "middle@order.test", _at(WINDOW_START + timedelta(days=3))
        )
        await seed_user(db_session, "oldest@order.test", _at(WINDOW_START))

        counts = await crud.get_recent_daily_counts(db_session, today=ANCHOR)

        assert [item.date for item in counts] == [
            day.isoformat() for day in window_dates()
        ]

    async def test_a_day_without_creations_reads_zero_between_days_that_have_them(
        self, db_session: AsyncSession
    ) -> None:
        """A quiet day is reported as zero, not skipped out of the series."""
        for step in range(3):
            await seed_user(
                db_session,
                f"busy-{step}@gap.test",
                _at(WINDOW_START + timedelta(days=step)),
            )
        await seed_user(
            db_session,
            "later@gap.test",
            _at(WINDOW_START + timedelta(days=6)),
        )

        counts = await crud.get_recent_daily_counts(db_session, today=ANCHOR)

        assert [item.count for item in counts] == [1, 1, 1, 0, 0, 0, 1]

    async def test_several_creations_on_one_day_are_counted_together(
        self, db_session: AsyncSession
    ) -> None:
        """Five registrations on one day are one data point carrying five."""
        for hour in range(5):
            await seed_user(
                db_session, f"hour{hour}@same-day.test", _at(WINDOW_START, hour)
            )

        counts = await crud.get_recent_daily_counts(db_session, today=ANCHOR)

        assert counts[0].model_dump() == {"date": WINDOW_START.isoformat(), "count": 5}
        assert sum(item.count for item in counts) == 5

    async def test_creations_before_the_window_are_left_out(
        self, db_session: AsyncSession
    ) -> None:
        """Day eight back is outside the window and does not reach the series."""
        await seed_user(db_session, "eight@edge.test", _at(WINDOW_START - timedelta(1)))
        await seed_user(db_session, "nine@edge.test", _at(WINDOW_START - timedelta(2)))

        counts = await crud.get_recent_daily_counts(db_session, today=ANCHOR)

        assert len(counts) == WINDOW_DAYS
        assert sum(item.count for item in counts) == 0

    async def test_soft_deleted_users_are_left_out_of_the_window(
        self, db_session: AsyncSession
    ) -> None:
        """A deleted registration is not a creation the window still counts."""
        await seed_user(db_session, "kept@window-delete.test", _at(WINDOW_START))
        await seed_user(
            db_session,
            "gone@window-delete.test",
            _at(WINDOW_START),
            deleted_at=datetime(2026, 2, 1, 9, 0, 0),
        )

        counts = await crud.get_recent_daily_counts(db_session, today=ANCHOR)

        assert [item.count for item in counts] == [1, 0, 0, 0, 0, 0, 0]

    async def test_every_data_point_is_a_day_and_an_integer_count(
        self, db_session: AsyncSession
    ) -> None:
        """The series is made of the data points the schema defines."""
        await seed_user(db_session, "one@shape.test", _at(ANCHOR - timedelta(2)))

        counts = await crud.get_recent_daily_counts(db_session, today=ANCHOR)

        assert all(isinstance(item, DailyCount) for item in counts)
        assert all(isinstance(item.count, int) for item in counts)
        assert all(
            item.date == date.fromisoformat(item.date).isoformat() for item in counts
        )


class TestCurrentDayInTheWindow:
    """The last day of the window: the current day, however far it has got."""

    async def test_the_current_day_is_the_last_point_even_when_it_is_half_over(
        self, db_session: AsyncSession
    ) -> None:
        """A day still under way is reported, counting what happened so far."""
        await seed_user(db_session, "early@partial.test", _at(ANCHOR, 0))
        await seed_user(db_session, "midmorning@partial.test", _at(ANCHOR, 9))

        counts = await crud.get_recent_daily_counts(db_session, today=ANCHOR)

        assert len(counts) == WINDOW_DAYS
        assert counts[-1].date == ANCHOR.isoformat()
        assert counts[-1].count == 2

    async def test_a_current_day_with_nothing_on_it_yet_reads_zero(
        self, db_session: AsyncSession
    ) -> None:
        """A day that has produced nothing so far is a zero, not a missing row."""
        await seed_user(
            db_session, "yesterday@partial.test", _at(ANCHOR - timedelta(1))
        )

        counts = await crud.get_recent_daily_counts(db_session, today=ANCHOR)

        assert counts[-1].model_dump() == {"date": ANCHOR.isoformat(), "count": 0}
        assert counts[-2].count == 1

    async def test_the_default_window_is_seven_days_ending_on_the_current_day(
        self, db_session: AsyncSession
    ) -> None:
        """With no day given, the window is the seven days ending today.

        This is the one check that reads the clock, and it is the check that
        says what the default means: the seven most recent UTC days, oldest
        first, the current one last.
        """
        today = datetime.now(UTC).date()

        counts = await crud.get_recent_daily_counts(db_session)

        assert len(counts) == WINDOW_DAYS
        assert counts[-1].date == today.isoformat()
        assert counts[0].date == (today - timedelta(days=WINDOW_DAYS - 1)).isoformat()
        assert [item.date for item in counts] == sorted(item.date for item in counts)


class TestWindowArguments:
    """The window's arguments: the length, and the day it is measured from."""

    async def test_the_window_length_follows_the_days_argument(
        self, db_session: AsyncSession
    ) -> None:
        """Asking for three days gets three days, oldest first, ending today."""
        counts = await crud.get_recent_daily_counts(db_session, days=3, today=ANCHOR)

        assert [item.date for item in counts] == [
            (ANCHOR - timedelta(days=step)).isoformat() for step in (2, 1, 0)
        ]

    async def test_a_window_of_one_day_is_the_current_day_alone(
        self, db_session: AsyncSession
    ) -> None:
        """The shortest honest window is today, on its own."""
        await seed_user(db_session, "today@single.test", _at(ANCHOR, 7))

        counts = await crud.get_recent_daily_counts(db_session, days=1, today=ANCHOR)

        assert [item.model_dump() for item in counts] == [
            {"date": ANCHOR.isoformat(), "count": 1}
        ]

    @pytest.mark.parametrize("days", [0, -1, -7])
    async def test_a_window_shorter_than_a_day_is_refused(
        self, db_session: AsyncSession, days: int
    ) -> None:
        """A window that holds no day is a bad argument, said as one.

        Args:
            db_session: The test's database session.
            days: The impossible window length.
        """
        with pytest.raises(ValueError, match="at least one day"):
            await crud.get_recent_daily_counts(db_session, days=days, today=ANCHOR)

    async def test_the_default_window_length_is_seven_days(self) -> None:
        """The module says seven days, so a caller who says nothing gets a week."""
        assert crud.DAILY_COUNT_WINDOW_DAYS == WINDOW_DAYS
