"""The analytics service layer (TASK-A0AE-004).

Everything below the service already exists: ``crud.get_recent_daily_counts``
aggregates creations by day and answers with a zero-filled window
(TASK-A0AE-001/-002), and ``GET /users/created-per-day`` puts an HTTP surface on
top of it (TASK-A0AE-003). What was missing is the layer in between — the thing
that decides what window to ask for, asks for it through an injectable data
source, and hands back a series whose shape does not depend on what the database
happened to hold. That layer is what this file pins.

* the service method answers with seven days covering the last seven days,
  oldest first and the current day last (AC-001),
* empty data is not an empty answer: a database with nothing in it, or a data
  source that returns nothing at all, still yields seven days carrying zero
  counts (AC-002).

The data source is injected, so half of these checks run against the real
database through the real CRUD layer and the other half run against a stand-in
that never touches one. Both halves must agree on the shape of the answer, which
is the point of having the service decide the shape rather than leaving it to
whatever the query returned.

The window is measured from a day handed in rather than from whatever today
happens to be, so the file says the same thing at 23:59 as it does at 00:01. The
one check that reads the real clock is the one that pins the default window.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.models import User
from src.users.schemas import DailyCount
from src.users.service import (
    ANALYTICS_WINDOW_DAYS,
    AnalyticsService,
    get_analytics_service,
)

# The day the window is measured from, fixed so a run says the same thing
# whatever today is, and the first of the seven days sitting behind it.
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


class RecordingSource:
    """A stand-in data source that remembers how the service called it.

    Stands in for the CRUD layer so the service's own decisions — which window
    it asked for, what it did with a short or empty answer — can be read off the
    call rather than inferred from a database.
    """

    def __init__(self, rows: list[DailyCount]) -> None:
        """Record the rows this source will hand back.

        Args:
            rows: The data points a call returns, in whatever order and however
                many the scenario calls for.
        """
        self.rows = rows
        self.calls: list[tuple[int, date | None]] = []

    async def __call__(
        self, db: AsyncSession, days: int, today: date | None
    ) -> list[DailyCount]:
        """Return the scripted rows, noting the window that was asked for.

        Args:
            db: The session the service was handed, unused by a scripted source.
            days: How many days the service asked for.
            today: The day the service measured the window from.

        Returns:
            The scripted rows.
        """
        self.calls.append((days, today))
        return list(self.rows)


class ExplodingSource:
    """A data source that fails the way an unavailable database fails."""

    async def __call__(
        self, db: AsyncSession, days: int, today: date | None
    ) -> list[DailyCount]:
        """Refuse to answer.

        Args:
            db: The session the service was handed, unused.
            days: How many days were asked for, unused.
            today: The day the window was measured from, unused.

        Raises:
            SQLAlchemyError: Always — this source cannot answer.
        """
        raise SQLAlchemyError("Database connection failed")


class TestServiceReturnsSevenDays:
    """AC-001: the service method answers with the last seven days."""

    async def test_seven_days_covering_the_last_seven_days(
        self, db_session: AsyncSession
    ) -> None:
        """The series is the seven days ending on the anchor day, oldest first."""
        service = AnalyticsService()

        counts = await service.get_daily_created_counts(db_session, today=ANCHOR)

        assert [entry.date for entry in counts] == [
            day.isoformat() for day in window_dates()
        ]

    async def test_each_day_carries_its_own_creations(
        self, db_session: AsyncSession
    ) -> None:
        """Counts land on the day they happened, and only on that day."""
        days = window_dates()
        await seed_user(db_session, "today-a@example.test", _at(days[-1]))
        await seed_user(db_session, "today-b@example.test", _at(days[-1], hour=23))
        await seed_user(db_session, "yesterday@example.test", _at(days[-2]))
        # Outside the window, and soft-deleted inside it: neither counts.
        await seed_user(
            db_session, "before@example.test", _at(days[0] - timedelta(days=4))
        )
        await seed_user(
            db_session,
            "gone@example.test",
            _at(days[-3]),
            deleted_at=_at(days[-3], hour=18),
        )
        service = AnalyticsService()

        counts = await service.get_daily_created_counts(db_session, today=ANCHOR)

        assert [entry.model_dump() for entry in counts] == [
            {"date": day.isoformat(), "count": expected}
            for day, expected in zip(days, [0, 0, 0, 0, 0, 1, 2], strict=True)
        ]

    async def test_the_default_window_is_the_seven_days_ending_today(
        self, db_session: AsyncSession
    ) -> None:
        """With no anchor given, the window ends on the current UTC day."""
        service = AnalyticsService()

        counts = await service.get_daily_created_counts(db_session)

        anchor = datetime.now(UTC).date()
        assert len(counts) == ANALYTICS_WINDOW_DAYS == WINDOW_DAYS
        assert counts[-1].date == anchor.isoformat()
        assert counts[0].date == (anchor - timedelta(days=WINDOW_DAYS - 1)).isoformat()

    async def test_the_window_length_is_the_caller_s_when_it_gives_one(
        self, db_session: AsyncSession
    ) -> None:
        """A caller asking for a different span gets that span, same rules."""
        service = AnalyticsService()

        counts = await service.get_daily_created_counts(
            db_session, days=3, today=ANCHOR
        )

        assert [entry.date for entry in counts] == [
            (ANCHOR - timedelta(days=offset)).isoformat() for offset in (2, 1, 0)
        ]

    async def test_a_source_that_cannot_answer_is_not_swallowed(
        self, db_session: AsyncSession
    ) -> None:
        """A failing data source surfaces to the caller rather than reading empty."""
        service = AnalyticsService(source=ExplodingSource())

        with pytest.raises(SQLAlchemyError):
            await service.get_daily_created_counts(db_session, today=ANCHOR)

    async def test_a_window_of_no_days_is_refused(
        self, db_session: AsyncSession
    ) -> None:
        """Zero or negative days describes no window, and says so."""
        service = AnalyticsService()

        for days in (0, -3):
            with pytest.raises(ValueError, match="at least one day"):
                await service.get_daily_created_counts(
                    db_session, days=days, today=ANCHOR
                )


class TestServiceHandlesEmptyData:
    """AC-002: empty data answers with seven zero counts, not with nothing."""

    async def test_an_empty_database_answers_with_seven_days_of_zeros(
        self, db_session: AsyncSession
    ) -> None:
        """Nothing created at all still produces the full seven-day series."""
        service = AnalyticsService()

        counts = await service.get_daily_created_counts(db_session, today=ANCHOR)

        assert [entry.model_dump() for entry in counts] == [
            {"date": day.isoformat(), "count": 0} for day in window_dates()
        ]

    async def test_a_source_that_returns_nothing_still_yields_seven_zero_days(
        self, db_session: AsyncSession
    ) -> None:
        """An empty answer from the data layer is padded out, not passed through."""
        source = RecordingSource(rows=[])
        service = AnalyticsService(source=source)

        counts = await service.get_daily_created_counts(db_session, today=ANCHOR)

        assert [entry.model_dump() for entry in counts] == [
            {"date": day.isoformat(), "count": 0} for day in window_dates()
        ]

    async def test_days_missing_from_the_answer_read_as_zero(
        self, db_session: AsyncSession
    ) -> None:
        """The days a query omits are the days that had nothing to count."""
        days = window_dates()
        source = RecordingSource(
            rows=[
                DailyCount(date=days[6], count=4),
                DailyCount(date=days[2], count=1),
            ]
        )
        service = AnalyticsService(source=source)

        counts = await service.get_daily_created_counts(db_session, today=ANCHOR)

        assert [entry.model_dump() for entry in counts] == [
            {"date": day.isoformat(), "count": expected}
            for day, expected in zip(days, [0, 0, 1, 0, 0, 0, 4], strict=True)
        ]

    async def test_rows_handed_back_out_of_order_are_put_in_order(
        self, db_session: AsyncSession
    ) -> None:
        """The series is ordered oldest to newest whatever the source's order was."""
        days = window_dates()
        source = RecordingSource(
            rows=[
                DailyCount(date=days[-1], count=2),
                DailyCount(date=days[0], count=1),
                DailyCount(date=days[3], count=3),
            ]
        )
        service = AnalyticsService(source=source)

        counts = await service.get_daily_created_counts(db_session, today=ANCHOR)

        assert [entry.date for entry in counts] == [
            day.isoformat() for day in window_dates()
        ]
        assert [entry.count for entry in counts] == [1, 0, 0, 3, 0, 0, 2]

    async def test_days_outside_the_window_are_left_out(
        self, db_session: AsyncSession
    ) -> None:
        """A source that over-answers does not lengthen the window."""
        source = RecordingSource(
            rows=[
                DailyCount(date=WINDOW_START - timedelta(days=30), count=9),
                DailyCount(date=ANCHOR, count=1),
            ]
        )
        service = AnalyticsService(source=source)

        counts = await service.get_daily_created_counts(db_session, today=ANCHOR)

        assert len(counts) == WINDOW_DAYS
        assert counts[-1].model_dump() == {"date": ANCHOR.isoformat(), "count": 1}


class TestServiceIsInjectable:
    """The service takes its data source from outside, and uses it."""

    async def test_the_injected_source_is_the_one_that_gets_called(
        self, db_session: AsyncSession
    ) -> None:
        """Injection is real: the stand-in answers, the database is untouched."""
        await seed_user(db_session, "ignored@example.test", _at(ANCHOR))
        source = RecordingSource(rows=[DailyCount(date=ANCHOR, count=99)])
        service = AnalyticsService(source=source)

        counts = await service.get_daily_created_counts(db_session, today=ANCHOR)

        assert source.calls == [(WINDOW_DAYS, ANCHOR)]
        assert counts[-1].count == 99

    async def test_the_anchor_is_resolved_once_and_passed_down(
        self, db_session: AsyncSession
    ) -> None:
        """The service fixes the day itself, so source and series cannot disagree."""
        source = RecordingSource(rows=[])
        service = AnalyticsService(source=source)

        await service.get_daily_created_counts(db_session)

        assert source.calls[0][1] == datetime.now(UTC).date()

    async def test_the_default_wiring_reads_the_real_database(
        self, db_session: AsyncSession
    ) -> None:
        """The dependency factory produces a service that reaches the database."""
        await seed_user(db_session, "default@example.test", _at(ANCHOR))
        service = get_analytics_service()

        counts = await service.get_daily_created_counts(db_session, today=ANCHOR)

        assert len(counts) == WINDOW_DAYS
        assert counts[-1] == DailyCount(date=ANCHOR, count=1)
