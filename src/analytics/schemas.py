"""Pydantic schemas for user-creation analytics.

The analytics served here is a daily series: one data point per calendar day,
ordered oldest first, as required by ``GET /users/created-per-day``
(FEAT-6F3D). The series is derived from the ``users`` table itself; see
:mod:`src.analytics.models` for that storage decision.
"""

from __future__ import annotations

from datetime import date as calendar_date
from datetime import datetime
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_validator,
    model_validator,
)


class UserCountByDate(BaseModel):
    """The number of users created on one calendar day."""

    date: Annotated[
        calendar_date,
        Field(description="Calendar date of the data point, in ISO-8601 (YYYY-MM-DD)."),
    ]
    count: Annotated[
        int,
        Field(ge=0, description="Users created on that day; never negative."),
    ]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "date": "2026-09-08",
                    "count": 5,
                }
            ]
        }
    )

    @field_validator("date", mode="before")
    @classmethod
    def normalise_timestamp(cls, value: object) -> object:
        """Reduce anything timestamp-shaped to the calendar day it falls on.

        A grouped query hands back a ``datetime`` on PostgreSQL and an ISO
        string on SQLite, so both have to land on the same ``date`` type
        before the data point can be compared, ordered or serialised.

        Args:
            value: The raw value supplied for ``date``.

        Returns:
            object: The day of the timestamp, or the value untouched when it
            is not timestamp-shaped, so that Pydantic reports the offending
            input in its own words.
        """
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.strip()).date()
            except ValueError:
                return value  # Not an ISO timestamp; Pydantic raises the error.
        return value


class CreatedPerDayResponse(RootModel[list[UserCountByDate]]):
    """The daily series returned by ``GET /users/created-per-day``.

    The body is a bare JSON array of data points, oldest first, which is the
    shape ASSUM-001 of the feature spec assumes and the contract named in the
    feature's implementation guide.
    """

    @model_validator(mode="after")
    def require_oldest_first(self) -> Self:
        """Refuse a series that is not one strictly ascending data point a day.

        Returns:
            Self: The validated series, untouched.

        Raises:
            ValueError: When a data point does not fall strictly later than
                the one before it, which would break the endpoint's promise
                to order the window oldest first.
        """
        points = self.root
        for position in range(1, len(points)):
            previous, current = points[position - 1], points[position]
            if current.date <= previous.date:
                msg = (
                    "data points must be ordered oldest first, one per day: "
                    f"{current.date.isoformat()} at position {position} does not "
                    f"follow {previous.date.isoformat()}"
                )
                raise ValueError(msg)
        return self


#: The name the feature's implementation guide uses for the data-point schema.
UserCount = UserCountByDate

__all__ = ["CreatedPerDayResponse", "UserCount", "UserCountByDate"]
