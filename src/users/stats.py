"""Daily user-creation statistics: the query layer behind GET /users/created-per-day.

TASK-D49B-002 of FEAT-D49B.  One function matters here:
:func:`get_daily_user_counts`, which aggregates the ``users`` table into one
:class:`~src.users.schemas.DailyUserCount` entry per day of a rolling window,
oldest day first.  The route of TASK-D49B-003 and the endpoint handler of
TASK-D49B-004 have only to serialise what this module returns.

Naming note: this is ``src.users.stats`` — user analytics.  It is unrelated to
``src.stats``, which counts HTTP requests served by the process.

Why the query counts with half-open datetime ranges rather than grouping by a
SQL date function: the two databases this project runs against disagree about
date functions and about the timezone a date is taken in (see the dialect
detection this problem forced in ``count_users_by_domain``), while a
``created_at >= midnight AND created_at < next midnight`` range is the same
question in both.  ``users.created_at`` is a plain ``TIMESTAMP``
(alembic/versions/a143501c5e1f_create_users_table.py), so the naive midnights
below line up with what is stored — the same approach ``crud.count_users_today``
uses, proven on both databases.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, case, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.models import User
from src.users.schemas import DailyUserCount

logger = logging.getLogger(__name__)

# Days in the rolling window the analytics endpoint exposes: today plus the six
# days before it (ASSUM-001 and ASSUM-002 of
# features/daily-user-creation-count — the current day counts even when it is
# still incomplete).
DEFAULT_WINDOW_DAYS = 7

# Ceiling on a requested window, so a mistyped or hostile query parameter
# cannot ask the database for an aggregation spanning years.
MAX_WINDOW_DAYS = 366

__all__ = ["DEFAULT_WINDOW_DAYS", "MAX_WINDOW_DAYS", "get_daily_user_counts"]


def _day_start(day: date) -> datetime:
    """Return midnight at the start of ``day`` as a naive datetime.

    Naive because ``users.created_at`` is a ``TIMESTAMP`` without a timezone,
    so comparing against a naive boundary compares like with like on both
    SQLite and PostgreSQL.

    Args:
        day: The calendar day to open.

    Returns:
        Midnight at the start of that day.
    """
    return datetime(day.year, day.month, day.day)


def _build_window(days: int, today: date) -> list[date]:
    """Build the requested window of calendar days, oldest day first.

    Args:
        days: How many days the window should span, including ``today``.
        today: The day that closes the window.

    Returns:
        ``days`` consecutive dates in ascending order, ending with ``today``.

    Raises:
        ValueError: If ``days`` is below one or above ``MAX_WINDOW_DAYS``.
    """
    if days < 1:
        raise ValueError(
            f"days must be at least 1 to build a daily-count window, got {days}"
        )
    if days > MAX_WINDOW_DAYS:
        raise ValueError(
            f"days must be at most {MAX_WINDOW_DAYS} so the aggregate stays "
            f"bounded, got {days}"
        )
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def _count_on(day: date) -> ColumnElement[int]:
    """Return the conditional aggregate counting users created on ``day``.

    One ``SUM(CASE WHEN ... THEN 1 ELSE 0 END)`` per day: the database does the
    counting, no date function is needed, and the day is described by the same
    half-open range as every other count in this package.

    Args:
        day: The calendar day to count creations on.

    Returns:
        A SQL aggregate expression yielding that day's count.
    """
    return func.sum(
        case(
            (
                and_(
                    User.created_at >= _day_start(day),
                    User.created_at < _day_start(day + timedelta(days=1)),
                ),
                1,
            ),
            else_=0,
        )
    )


async def get_daily_user_counts(
    db: AsyncSession, days: int = DEFAULT_WINDOW_DAYS
) -> list[DailyUserCount]:
    """Count users created on each day of a rolling window, oldest day first.

    The window is the last ``days`` calendar days including today, so an
    incomplete current day is reported like any other (its count covers only
    what happened so far).  Every day in the window gets an entry whether or not
    anyone was created on it: a day with no creations is reported with a count
    of zero rather than omitted, which is what keeps an empty dataset valid
    output — ``days`` entries, all zero — instead of an empty list.

    Soft-deleted users are excluded, as every other count in this package
    excludes them (``crud.count_users``, ``crud.count_users_today``,
    ``crud.count_users_by_domain``), and users created outside the window —
    older than it, or stamped in the future — are not reported at all.

    Args:
        db: The async database session.
        days: Size of the window in days, today included (default 7).

    Returns:
        ``days`` :class:`DailyUserCount` entries in ascending date order, the
        oldest day first and today last.

    Raises:
        ValueError: If ``days`` is below one or above ``MAX_WINDOW_DAYS``.
        SQLAlchemyError: If the aggregate query fails.
    """
    window = _build_window(days, date.today())
    window_start = _day_start(window[0])
    window_end = _day_start(window[-1] + timedelta(days=1))

    buckets: list[ColumnElement[int]] = [
        _count_on(day).label(f"day_{index}") for index, day in enumerate(window)
    ]
    stmt: Select[Any] = (
        select(*buckets)
        .select_from(User)
        .where(User.created_at >= window_start)
        .where(User.created_at < window_end)
        .where(User.deleted_at.is_(None))
    )

    try:
        result = await db.execute(stmt)
    except SQLAlchemyError:
        logger.exception(
            "Daily user-count aggregate failed for a %d-day window ending %s",
            days,
            window[-1],
        )
        raise

    # An aggregate without GROUP BY yields exactly one row, holding NULL when
    # the table is empty — which reads back as a zero count, not a missing day.
    return [
        DailyUserCount(date=day, count=int(count or 0))
        for day, count in zip(window, result.one(), strict=True)
    ]
