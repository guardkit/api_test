"""Pydantic schemas for user creation analytics.

Declares the response shape of ``GET /users/created-per-day``: a JSON array of
entries, one per day, each holding an ISO-8601 ``date`` and the integer
``count`` of users created on that day. The window (the last 7 days, oldest
first, soft-deleted users included) is the query's business, not this module's.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, RootModel, field_validator

# What the date key accepts before validation: the ISO-8601 string itself, or
# the date/datetime a query layer is likely to hand back.
DateLike = date | datetime | str


class UserCreatedPerDayEntry(BaseModel):
    """Schema for one day's user creation count."""

    date: str
    count: int

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "date": "2026-10-03",
                    "count": 42,
                }
            ]
        }
    )

    @field_validator("date", mode="before")
    @classmethod
    def format_date(cls, v: DateLike) -> str:
        """Normalize a date or datetime to an ISO-8601 string."""
        if isinstance(v, datetime):
            return v.date().isoformat()
        if isinstance(v, date):
            return v.isoformat()
        return v


class UserCreatedPerDayResponse(RootModel[list[UserCreatedPerDayEntry]]):
    """Schema for the created-per-day response: a list of day entries.

    Serializes as a bare JSON array of ``{"date": ..., "count": ...}`` objects,
    i.e. ``list[dict[str, str | int]]``.
    """

    root: list[UserCreatedPerDayEntry]
