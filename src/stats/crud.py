"""CRUD operations for user creation statistics.

Provides database queries for the stats feature.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_users_created_per_day_counts(
    db: AsyncSession,
    start_date: date,
    end_date: date,
) -> Sequence[Sequence]:
    """Return user creation counts grouped by date.

    Queries the ``users`` table for rows whose ``created_at`` falls within
    the half-open interval ``[start_date, end_date)`` and returns the raw
    result rows as ``(day, count)`` tuples.

    Args:
        db: The async database session.
        start_date: Inclusive start of the date window.
        end_date: Exclusive end of the date window.

    Returns:
        Sequence of (day, count) rows ordered by day ascending.
    """
    query = text(
        "SELECT CAST(created_at AS DATE) AS day, COUNT(*) AS cnt "
        "FROM users "
        "WHERE created_at >= :start AND created_at < :end "
        "GROUP BY CAST(created_at AS DATE) "
        "ORDER BY day ASC"
    )
    result = await db.execute(
        query,
        {"start": start_date, "end": end_date},
    )
    return result.fetchall()
