"""Database access layer for the daily user-creation series (TASK-6F3D-002).

This is the query layer behind ``GET /users/created-per-day``: it answers the
last seven calendar days of user creations, oldest first, from the ``users``
table. Analytics stores nothing of its own (see the package docstring in
``src/analytics/__init__.py``), so every row it counts belongs to the users
feature and is read through that feature's public read interface —
``src.users.crud.count_users_created_per_day`` — never through
``src.users.models`` (ADR-001, amendment of 2026-08-31).

Two decisions live here rather than in the router or the service:

* **The window is exactly seven days, ending today (UTC).** The feature spec
  states it as a constraint ("Must return exactly 7 data points representing
  the last 7 days"), so a day with no creations still gets a data point with a
  count of zero. A grouped ``COUNT`` only returns the days that have rows, so
  the window is built first and the query's rows are laid over it.
* **The series is ordered oldest first**, both in the SQL (``ORDER BY`` the
  grouped day) and in the window that the query is laid over; the response
  schema refuses an out-of-order or repeated day outright, so an ordering
  regression cannot pass silently.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.analytics.schemas import CreatedPerDayResponse, UserCountByDate
from src.users.crud import count_users_created_per_day

#: Days in the rolling window the daily-count analytics answers with.
DAILY_WINDOW_DAYS = 7


def utc_today() -> date:
    """Today's calendar day in UTC, the timezone this analytics works in.

    Returns:
        date: The current UTC date, ignoring the time of day.
    """
    return datetime.now(tz=UTC).date()


def day_start(day: date) -> datetime:
    """The first instant of a calendar day, as the column stores it.

    ``users.created_at`` is a naive UTC timestamp column, so window bounds are
    handed to the query naive — the same convention ``src.users.crud`` uses in
    ``count_users_today``.

    Args:
        day: The calendar day to reduce to its first instant.

    Returns:
        datetime: Midnight at the start of ``day``, without a tzinfo.
    """
    return datetime(day.year, day.month, day.day)


def daily_window(
    end_date: date | None = None, days: int = DAILY_WINDOW_DAYS
) -> list[date]:
    """The calendar days of the analytics window, oldest first.

    Args:
        end_date: Last day of the window, or None for today (UTC).
        days: How many consecutive days the window spans.

    Returns:
        list[date]: ``days`` consecutive days ending at ``end_date``, oldest
        first, so the window is what gets counted regardless of what the
        database holds.

    Raises:
        ValueError: If ``days`` is below one, which would describe no window
            at all.
    """
    if days < 1:
        msg = f"the analytics window must span at least one day, got {days}"
        raise ValueError(msg)

    last_day = utc_today() if end_date is None else end_date
    return [last_day - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


async def get_users_created_per_day(
    db: AsyncSession,
    *,
    end_date: date | None = None,
    days: int = DAILY_WINDOW_DAYS,
) -> CreatedPerDayResponse:
    """Count user creations for each day of the rolling window, oldest first.

    Args:
        db: The async database session.
        end_date: Last day of the window, or None for today (UTC).
        days: How many days the window spans; seven answers the endpoint.

    Returns:
        CreatedPerDayResponse: Exactly ``days`` data points, one per calendar
        day of the window, oldest first, each count a non-negative integer.
        Days with no creation carry a count of zero rather than being missing.

    Raises:
        ValueError: If ``days`` is below one.
        SQLAlchemyError: If the database refuses or fails the query; it is
            reported by the caller, never swallowed here.
    """
    window = daily_window(end_date=end_date, days=days)

    rows = await count_users_created_per_day(
        db,
        start=day_start(window[0]),
        end=day_start(window[-1] + timedelta(days=1)),
    )

    counted = dict(rows)
    return CreatedPerDayResponse(
        [UserCountByDate(date=day, count=counted.get(day, 0)) for day in window]
    )


__all__ = [
    "DAILY_WINDOW_DAYS",
    "daily_window",
    "get_users_created_per_day",
]
