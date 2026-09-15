"""Service layer for user-creation analytics (TASK-A0AE-004).

This is the layer between the route and the query. The query
(:func:`src.users.crud.get_recent_daily_counts`) knows how to count creations
per day over a window; the route knows how to answer HTTP. Neither of them
should be the place that decides what the analytics series *is* — how long it
runs, which day it is measured from, and what a day with nothing in it reads as.
That decision lives here, so the endpoint and any future caller of the same
numbers agree on the shape of the answer.

Two things follow from putting the decision here:

* **The window is resolved once.** The service picks the day it measures from
  before anything is read, then passes that same day down. A request that
  straddles midnight cannot get a window from the query and a window from the
  service that name different days.
* **The shape is the service's promise, not the database's.** The series is
  built from the window and the returned rows are looked up in it, so a day with
  no creations reads as zero and an empty database answers with seven days of
  zeros rather than with an empty list.

The data source is injected. By default it is the CRUD layer; a caller — a test
above all — can hand in anything callable with the same shape and read the
service's behaviour off it without a database in sight. Per ADR-001 this file is
private to the users feature: other features import ``crud.py`` and
``schemas.py``, not this.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.crud import DAILY_COUNT_WINDOW_DAYS
from src.users.schemas import DailyCount, to_iso_date

logger = logging.getLogger(__name__)

# How many days the analytics series covers when the caller does not say.
# Aliased from the CRUD layer's own constant so the two halves of the feature
# cannot drift apart into two different ideas of "the last week".
ANALYTICS_WINDOW_DAYS: int = DAILY_COUNT_WINDOW_DAYS

# A source is whatever can answer "how many users were created on each of the
# ``days`` days ending on ``today``?" — the CRUD function fits, and so does any
# stand-in a test writes. ``today`` is resolved by the service, never by the
# source, so a source is handed the day to measure from rather than a choice.
DailyCountSource = Callable[
    [AsyncSession, int, date | None], Awaitable[list[DailyCount]]
]


async def _recent_daily_counts(
    db: AsyncSession, days: int, today: date | None
) -> list[DailyCount]:
    """Read the window through the CRUD layer.

    The lookup goes through the module attribute when this runs rather than
    through a reference captured at import, so a test that replaces
    :func:`src.users.crud.get_recent_daily_counts` still steers the default
    wiring.

    Args:
        db: The session to read through.
        days: How many consecutive days the window spans.
        today: The day to measure the window from.

    Returns:
        The days the CRUD layer counted, oldest first.
    """
    return await crud.get_recent_daily_counts(db, days=days, today=today)


class AnalyticsService:
    """Coordinates the retrieval of user-creation analytics.

    The service holds no state beyond the data source it was built with, so one
    instance can serve any number of requests, and any instance can be built
    around a stand-in source.
    """

    def __init__(self, source: DailyCountSource = _recent_daily_counts) -> None:
        """Build the service around a source of daily counts.

        Args:
            source: Whatever answers the daily-count question. Defaults to the
                CRUD layer, which is what the application runs with; a test can
                hand in a stand-in of the same shape.
        """
        self._source = source

    async def get_daily_created_counts(
        self,
        db: AsyncSession,
        days: int = ANALYTICS_WINDOW_DAYS,
        today: date | None = None,
    ) -> list[DailyCount]:
        """Return how many users were created on each day of the recent window.

        The window is the ``days`` consecutive days ending on the current day,
        and the answer is exactly ``days`` long: every day of it appears, oldest
        first and the current day last, carrying its count or zero when nobody
        registered on it. An empty database therefore answers with seven days of
        zeros, and a source that answers with only the days it found rows for is
        padded out to the same shape here.

        Args:
            db: The session the source reads through. Unused by a source that
                needs no database, but always passed down.
            days: How many consecutive days the window spans, counting the
                current one. Defaults to :data:`ANALYTICS_WINDOW_DAYS`.
            today: The day to measure the window from. Defaults to the current
                UTC day, which is the day ``users.created_at`` is written in.

        Returns:
            Exactly ``days`` data points, oldest day first, with zero counts on
            the days that had nothing to count.

        Raises:
            ValueError: When ``days`` is smaller than one, which describes no
                window at all.
            sqlalchemy.exc.SQLAlchemyError: When the source cannot answer. The
                service lets a database failure through rather than reporting it
                as an empty window — a caller that cannot ask is not a caller
                that heard nothing.
        """
        if days < 1:
            raise ValueError(
                f"The analytics window must span at least one day, got days={days}."
            )

        # Resolved here, once, and handed down: the day the window is measured
        # from must be the same day the source counted from and the day the
        # series is written against, or the last entry could name a day the
        # query never looked at.
        anchor = datetime.now(UTC).date() if today is None else today
        start = anchor - timedelta(days=days - 1)

        rows = await self._source(db, days, anchor)
        counted = {entry.date: int(entry.count) for entry in rows}

        # The window's days, written the same way the rows above are keyed, so a
        # day matches whatever shape the source handed that day back in. A day
        # the source did not mention had nothing to count, and reads zero; days
        # outside the window are dropped rather than lengthening the series.
        window = [to_iso_date(start + timedelta(days=step)) for step in range(days)]
        missing = [day for day in window if day not in counted]
        if missing:
            logger.debug(
                "Padding %d of %d day(s) in %s..%s with zero counts",
                len(missing),
                days,
                window[0],
                window[-1],
            )
        return [DailyCount(date=day, count=counted.get(day, 0)) for day in window]


def get_analytics_service() -> AnalyticsService:
    """Provide the analytics service, for injection into a route handler.

    The service is stateless apart from its source, so building one per request
    costs nothing and keeps a request from sharing state with the next. A test
    can replace this dependency wholesale through ``app.dependency_overrides``.

    Returns:
        An :class:`AnalyticsService` wired to the CRUD layer.
    """
    return AnalyticsService()


__all__ = ["ANALYTICS_WINDOW_DAYS", "AnalyticsService", "get_analytics_service"]
