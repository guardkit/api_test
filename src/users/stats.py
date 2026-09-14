"""Daily user-creation statistics: the read model behind GET /users/created-per-day.

TASK-D49B-002 of FEAT-D49B.  One function matters here:
:func:`get_daily_user_counts`, which reports the ``users`` table as one
:class:`~src.users.schemas.DailyUserCount` entry per day of a rolling window,
oldest day first.  The route of TASK-D49B-003 and the endpoint handler of
TASK-D49B-004 have only to serialise what this module returns.

Naming note: this is ``src.users.stats`` — user analytics.  It is unrelated to
``src.stats``, which counts HTTP requests served by the process.

Where the SQL lives: the query itself is ``crud.count_users_created_on_days``,
because this repository's architecture record puts database operations in the
feature's ``crud.py`` (docs/architecture/00-system-overview.md, section
"Architectural Layers").  What lives here is the policy around that query — how
wide the window is, which days it holds, that a day nobody was created on is
still a day worth reporting, and what a failed query is allowed to look like to
the caller — plus turning the row of per-day buckets back into schema objects.
The same division as ``crud.count_users_today``: crud asks the database, the
caller decides what the answer means.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
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

    try:
        counts = await crud.count_users_created_on_days(db, window)
    except SQLAlchemyError:
        # A failed query has to reach the caller as a failure. Seven zero counts
        # read out of a database that never answered would be the one answer
        # worse than an exception: indistinguishable from a genuinely quiet week.
        logger.exception(
            "Daily user-count aggregate failed for a %d-day window ending %s",
            days,
            window[-1],
        )
        raise

    return [
        DailyUserCount(date=day, count=count)
        for day, count in zip(window, counts, strict=True)
    ]
