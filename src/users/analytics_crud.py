"""Analytics queries over the ``users`` table.

Backs ``GET /users/created-per-day``. The window is the last seven calendar
days — today and the six days before it — oldest first, and it counts every row
of the table, soft-deleted users included. The response shape is declared in
src/users/analytics_schemas.py; this module only produces the rows.

The query is one round trip with one conditional aggregate per day, rather than
seven counts or a grouped date function. Grouping on a date function would need
a dialect branch — PostgreSQL has ``date_trunc``, SQLite has ``date`` — and the
conditional-sum form is standard SQL both drivers accept. It also keeps days
with no users in the result, which a ``GROUP BY`` would silently drop.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.models import User

# Today plus the six days before it.
WINDOW_DAYS = 7


def _window(days: int = WINDOW_DAYS) -> list[tuple[date, datetime, datetime]]:
    """Build the window's days, oldest first, with each day's bounds.

    The bounds are naive datetimes at midnight of the day and midnight of the
    day after it, matching the naive ``created_at`` column the way
    ``crud.count_users_today`` does. ``end`` is exclusive.

    Args:
        days: Number of calendar days in the window, including today.

    Returns:
        One ``(day, start, end)`` tuple per day, oldest day first.
    """
    today = date.today()
    window: list[tuple[date, datetime, datetime]] = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        start = datetime.combine(day, time.min)
        end = datetime.combine(day + timedelta(days=1), time.min)
        window.append((day, start, end))
    return window


async def get_created_per_day(db: AsyncSession) -> list[dict[str, int | date]]:
    """Count users created on each day of the window, oldest first.

    No ``deleted_at`` filter is applied, so soft-deleted users are counted just
    like live ones — the deliberate difference from the count queries in
    src/users/crud.py. Days with no users are present with a count of 0.

    Args:
        db: The async database session.

    Returns:
        One dict per day, oldest first, each with the calendar day under
        ``date`` and the number of users created on it under ``count``.
    """
    window = _window()

    columns = [
        func.coalesce(
            func.sum(
                case(
                    ((User.created_at >= start) & (User.created_at < end), 1),
                    else_=0,
                )
            ),
            0,
        ).label(f"day_{index}")
        for index, (_day, start, end) in enumerate(window)
    ]

    # The range predicate keeps the scan to the window; the conditional sums
    # above do the bucketing. Both are needed: the predicate alone cannot say
    # which day a row fell in.
    stmt = (
        select(*columns)
        .select_from(User)
        .where(User.created_at >= window[0][1])
        .where(User.created_at < window[-1][2])
    )
    row = (await db.execute(stmt)).one()

    return [
        {"date": day, "count": int(row[index])}
        for index, (day, _start, _end) in enumerate(window)
    ]
