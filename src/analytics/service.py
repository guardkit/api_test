"""Analytics service layer: assembling the daily user-creation series (TASK-6F3D-004).

This is the layer ``GET /users/created-per-day`` answers from: it decides what
window to ask about, asks the query layer for it, and turns the rows that come
back into the seven data points the endpoint promises (FEAT-6F3D). The
architecture record names ``service.py`` the file that "orchestrates business
logic, complex operations, and cross-entity coordination"
(docs/architecture/00-system-overview.md), and ADR-001 allows one per feature
rather than requiring it — this is the analytics feature's.

What lives here, and what does not:

* **The window is asked for, not assumed.** ``daily_window`` (the query layer's
  primitive, seven UTC days ending today) is resolved once per request and
  ``window_bounds`` turns it into the half-open ``[start, end)`` range the
  day-grouping query takes, so the query never counts a row twice and never
  counts a row the reply will not show.
* **The window, not the rows, decides the shape of the reply.** A grouped
  ``COUNT`` answers only the days that have rows; ``build_daily_series`` lays
  those rows over the window and zero-fills the rest, which is why an empty
  database still answers seven data points rather than none.
* **Formatting is a step of its own.** ``to_calendar_day`` normalises the three
  shapes a grouped day arrives in — a ``date`` on PostgreSQL, an ISO string on
  SQLite, a ``datetime`` from an expression — and ``iso_date`` states the
  ISO-8601 form the contract serialises to, so the day a caller reads is the
  day the row fell on regardless of the database underneath.

The service holds no session and opens no transaction: the caller hands one in,
exactly as the router's ``get_db`` dependency does (ADR-006). That is also what
keeps this logic testable without a database — every function but
``get_users_created_per_day`` answers plain data, and that one takes the
retrieval through ``src.users.crud.count_users_created_per_day``, the users
feature's public read interface, rather than around it to
``src.users.models`` (ADR-001, amendment of 2026-08-31).

Errors are reported, never swallowed: a database that refuses the query raises
``SQLAlchemyError`` through here for the router to answer as 503, and a window
or a row that cannot describe a series raises where it is detected.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import TypeAlias

from sqlalchemy.ext.asyncio import AsyncSession

from src.analytics.crud import DAILY_WINDOW_DAYS, daily_window, day_start
from src.analytics.schemas import CreatedPerDayResponse, UserCountByDate
from src.users.crud import count_users_created_per_day

logger = logging.getLogger(__name__)

#: The shapes a counted day arrives in: a calendar day, a timestamp that falls
#: on one, or the ISO-8601 text a database answers with.
DayLike: TypeAlias = date | datetime | str


def to_calendar_day(value: DayLike) -> date:
    """Reduce a counted day to the calendar day it falls on.

    Args:
        value: The day as it came back from the query, or as a caller wrote it.

    Returns:
        date: The calendar day ``value`` names, in UTC terms, since
        ``users.created_at`` stores naive UTC timestamps.

    Raises:
        ValueError: If text is not an ISO-8601 date or timestamp, which would
            otherwise be read as a different day than the one it names.
        TypeError: If the value is neither a day, a timestamp, nor text — a
            count or an unrelated object, most likely a row read sideways.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip()).date()
        except ValueError as exc:
            msg = f"not an ISO-8601 date or timestamp: {value!r}"
            raise ValueError(msg) from exc
    if isinstance(value, date):
        return value

    msg = f"cannot read a calendar day from {type(value).__name__}: {value!r}"
    raise TypeError(msg)


def iso_date(value: DayLike) -> str:
    """Format a day as the ISO-8601 calendar date the contract serialises to.

    Args:
        value: The day, timestamp, or ISO-8601 text to format.

    Returns:
        str: The day as ``YYYY-MM-DD``, with no time component, which is the
        form every data point's ``date`` field leaves the endpoint in.

    Raises:
        ValueError: If ``value`` is text that is not an ISO-8601 date.
        TypeError: If ``value`` is not a day-shaped object at all.
    """
    return to_calendar_day(value).isoformat()


def format_data_point(day: DayLike, count: int) -> UserCountByDate:
    """Build one validated data point of the daily series.

    Args:
        day: The calendar day the count belongs to, in any of the shapes
            ``to_calendar_day`` reads.
        count: How many users were created on that day.

    Returns:
        UserCountByDate: The data point, its day reduced to a calendar day and
        its count checked, ready to serialise with an ISO-8601 ``date``.

    Raises:
        ValueError: If ``count`` is negative, which no set of rows can produce
            and which would otherwise be served as a real day's total.
        TypeError: If ``day`` is not a day-shaped object.
    """
    calendar_day = to_calendar_day(day)
    if count < 0:
        msg = (
            f"a daily user count cannot be negative: got {count} "
            f"for {iso_date(calendar_day)}"
        )
        raise ValueError(msg)

    return UserCountByDate(date=calendar_day, count=count)


def window_bounds(window: Sequence[date]) -> tuple[datetime, datetime]:
    """Bound a window with the half-open range the day-grouping query takes.

    Args:
        window: The window's days, oldest first.

    Returns:
        tuple[datetime, datetime]: Midnight on the first day and midnight after
        the last, so the range covers every day of the window and no instant
        outside it — ``[start, end)``, the convention
        ``src.users.crud.count_users_created_per_day`` documents.

    Raises:
        ValueError: If the window is empty, which bounds nothing, or if it does
            not ascend, which would ask the query for a backwards range.
    """
    if not window:
        msg = "the daily window must span at least one day, got none"
        raise ValueError(msg)
    if len(window) > 1 and window[-1] <= window[0]:
        msg = (
            "the daily window must ascend: "
            f"{iso_date(window[0])} is not before {iso_date(window[-1])}"
        )
        raise ValueError(msg)

    return day_start(window[0]), day_start(window[-1] + timedelta(days=1))


def build_daily_series(
    counts: Iterable[tuple[DayLike, int]] | Mapping[DayLike, int],
    *,
    window: Sequence[date] | None = None,
    end_date: date | None = None,
    days: int = DAILY_WINDOW_DAYS,
) -> CreatedPerDayResponse:
    """Lay counted days over a window, oldest first, zero-filling the gaps.

    Args:
        counts: The counted rows — ``(day, count)`` pairs, or a day-to-count
            mapping. Days outside the window are dropped, and days the query
            did not answer are treated as zero rather than missing.
        window: The days to answer, oldest first, or None to resolve the window
            from ``end_date`` and ``days``.
        end_date: Last day of the window when ``window`` is not given, or None
            for today (UTC).
        days: How many days the window spans when ``window`` is not given.

    Returns:
        CreatedPerDayResponse: One data point per day of the window, oldest
        first, each count a non-negative integer.

    Raises:
        ValueError: If the window is empty, or if a counted count is negative.
        TypeError: If a counted day is not day-shaped.
    """
    resolved = (
        daily_window(end_date=end_date, days=days) if window is None else list(window)
    )
    if not resolved:
        msg = "the daily series needs a window of at least one day, got none"
        raise ValueError(msg)

    pairs: Iterable[tuple[DayLike, int]] = (
        counts.items() if isinstance(counts, Mapping) else counts
    )
    counted: dict[date, int] = {}
    for raw_day, raw_count in pairs:
        calendar_day = to_calendar_day(raw_day)
        # A grouped query answers one row per day, so adding only matters for
        # hand-built input; taking the last value would drop a day's rows.
        counted[calendar_day] = counted.get(calendar_day, 0) + raw_count

    return CreatedPerDayResponse(
        [format_data_point(day, counted.get(day, 0)) for day in resolved]
    )


async def get_users_created_per_day(
    db: AsyncSession,
    *,
    end_date: date | None = None,
    days: int = DAILY_WINDOW_DAYS,
) -> CreatedPerDayResponse:
    """Answer the daily user-creation series for the rolling window.

    The orchestration the endpoint runs: resolve the window, bound the query
    with it, retrieve the counted rows through the users feature's public read
    interface, and format them into the series.

    Args:
        db: The async database session, supplied by the caller (ADR-006); the
            service opens nothing of its own.
        end_date: Last day of the window, or None for today (UTC).
        days: How many days the window spans; seven answers the endpoint.

    Returns:
        CreatedPerDayResponse: Exactly ``days`` data points, oldest first, with
        ISO-8601 dates and non-negative counts. Days with no creation carry a
        count of zero rather than being absent, so the reply never depends on
        how much history the database happens to hold.

    Raises:
        ValueError: If ``days`` is below one, or if a retrieved row cannot
            describe a data point.
        SQLAlchemyError: If the database refuses or fails the query; it is
            reported by the caller — the router answers it as 503 — never
            swallowed into a short series here.
    """
    window = daily_window(end_date=end_date, days=days)
    start, end = window_bounds(window)

    logger.debug(
        "assembling the daily user-creation series for %s..%s (%d days)",
        iso_date(window[0]),
        iso_date(window[-1]),
        len(window),
    )

    rows = await count_users_created_per_day(db, start, end)
    series = build_daily_series(rows, window=window)

    logger.debug(
        "the daily user-creation series covers %s..%s with %d creations",
        iso_date(window[0]),
        iso_date(window[-1]),
        sum(point.count for point in series.root),
    )

    return series


__all__ = [
    "DAILY_WINDOW_DAYS",
    "build_daily_series",
    "daily_window",
    "format_data_point",
    "get_users_created_per_day",
    "iso_date",
    "to_calendar_day",
    "window_bounds",
]
