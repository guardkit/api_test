"""User creation statistics endpoint.

Provides GET /stats/users-created-per-day for retrieving user creation
counts over the last 7 days.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_db
from src.stats.crud import get_users_created_per_day_counts

router = APIRouter(tags=["stats"])


class UsersCreatedPerDay(BaseModel):
    """A single day's user creation count.

    Attributes:
        date: The date in YYYY-MM-DD format.
        count: Number of users created on that date.
    """

    date: str = Field(description="Date in YYYY-MM-DD format")
    count: int = Field(description="Number of users created on this date")


@router.get(
    "/stats/users-created-per-day",
    response_model=list[UsersCreatedPerDay],
    summary="Users created per day (last 7 days)",
)
async def get_users_created_per_day(
    db: AsyncSession = Depends(get_db),
) -> list[UsersCreatedPerDay]:
    """Return user creation counts for the last 7 days.

    Returns exactly 7 data points covering the most recent 7-day window
    (today going back 6 days), ordered oldest first. Days with no new
    users are reported with a count of zero.

    Args:
        db: The async database session (injected by FastAPI).

    Returns:
        List of 7 ``UsersCreatedPerDay`` entries, oldest first.
    """
    today = date.today()
    start_date = today - timedelta(days=6)

    # Generate all 7 dates to ensure we always return exactly 7 entries
    all_dates: list[date] = [today - timedelta(days=i) for i in range(6, -1, -1)]
    date_to_count: dict[str, int] = {d.isoformat(): 0 for d in all_dates}

    # Delegate to CRUD layer
    rows = await get_users_created_per_day_counts(db, start_date, today + timedelta(days=1))
    for row in rows:
        day_str = str(row[0])
        cnt = int(row[1])
        if day_str in date_to_count:
            date_to_count[day_str] = cnt

    # Return in date order (oldest first)
    result_list = [
        UsersCreatedPerDay(
            date=d.isoformat(),
            count=date_to_count[d.isoformat()],
        )
        for d in all_dates
    ]
    return result_list
