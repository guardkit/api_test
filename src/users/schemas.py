"""Pydantic schemas for users."""

from __future__ import annotations

from datetime import UTC, datetime
from datetime import date as CalendarDay
from typing import TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

# Pydantic refuses a field whose name is also a type name, so the calendar-day
# type behind the ``date`` fields below is imported under an alias and named
# once here for both daily-count schemas to use.
DayType: TypeAlias = CalendarDay


class UserBase(BaseModel):
    """Base schema for user operations."""

    email: EmailStr
    full_name: str | None = None


class UserCreate(UserBase):
    """Schema for creating a new user.

    Automatically derives the domain from the email address.
    """

    domain: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "john.doe@example.com",
                    "full_name": "John Doe",
                }
            ]
        }
    )

    @model_validator(mode="after")
    def populate_domain(self) -> UserCreate:
        """Derive domain from email address."""
        if self.domain is None and self.email:
            self.domain = self.email.split("@")[-1].lower()
        return self


class DomainCountResponse(BaseModel):
    """Schema for domain count entries."""

    domain: str
    count: int

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "domain": "example.com",
                    "count": 5,
                }
            ]
        }
    )


class UserUpdate(BaseModel):
    """Schema for updating an existing user."""

    email: EmailStr | None = None
    full_name: str | None = None
    is_active: bool | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "john.doe@example.com",
                    "full_name": "John Doe",
                    "is_active": True,
                }
            ]
        }
    )


class UserPublic(BaseModel):
    """Schema for user responses.

    Includes id, name (derived from full_name), and email as per ASSUM-001.
    """

    id: str
    email: EmailStr
    domain: str | None = None
    name: str | None = None
    full_name: str | None = None
    is_active: bool = True
    created_at: str
    updated_at: str
    deleted_at: str | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "john.doe@example.com",
                    "full_name": "John Doe",
                    "is_active": True,
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "deleted_at": None,
                }
            ]
        },
    )

    @field_validator("created_at", "updated_at", "deleted_at", mode="before")
    @classmethod
    def format_datetime(cls, v: datetime | str) -> str:
        """Format datetime to ISO format string."""
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    @model_validator(mode="after")
    def populate_name_from_full_name(self) -> UserPublic:
        """Populate the name field from full_name if name is not set.

        Ensures the response includes 'name' as required by ASSUM-001.
        """
        if self.name is None and self.full_name is not None:
            self.name = self.full_name
        return self


class UserCountResponse(BaseModel):
    """Schema for user count responses."""

    count: int

    model_config = ConfigDict(json_schema_extra={"examples": [{"count": 42}]})


class UserSummaryResponse(BaseModel):
    """Schema for user summary responses."""

    username: str
    display_name: str
    profile_metadata: dict[str, str]
    days_since_created: int
    is_active: bool = True

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "username": "john.doe@example.com",
                    "display_name": "John Doe",
                    "profile_metadata": {
                        "email": "john.doe@example.com",
                        "status": "active",
                    },
                    "days_since_created": 365,
                    "is_active": True,
                }
            ]
        }
    )


class UserList(BaseModel):
    """Schema for paginated user list responses."""

    items: list[UserPublic]
    total: int

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "items": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "email": "john.doe@example.com",
                            "full_name": "John Doe",
                            "is_active": True,
                            "created_at": "2024-01-01T00:00:00Z",
                            "updated_at": "2024-01-01T00:00:00Z",
                            "deleted_at": None,
                        }
                    ],
                    "total": 1,
                }
            ]
        }
    )


class RecentUsersResponse(BaseModel):
    """Schema for recent users responses."""

    users: list[UserPublic]
    total: int

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "users": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "email": "john.doe@example.com",
                            "full_name": "John Doe",
                            "is_active": True,
                            "created_at": "2024-01-01T00:00:00Z",
                            "updated_at": "2024-01-01T00:00:00Z",
                            "deleted_at": None,
                        }
                    ],
                    "total": 1,
                }
            ]
        }
    )


def _calendar_day_of(moment: datetime) -> DayType:
    """Return the calendar day a timestamp falls on.

    A timezone-aware timestamp is read in UTC, which is how the rest of this
    package turns a timestamp into a day; a naive one is taken at face value.

    Args:
        moment: The timestamp to read a day out of.

    Returns:
        The calendar day the timestamp falls on.
    """
    if moment.tzinfo is not None:
        return moment.astimezone(UTC).date()
    return moment.date()


def _timestamp_in(text: str) -> datetime | None:
    """Return the timestamp an ISO-8601 string carries, or None.

    A database driver may hand back a timestamp either as a ``datetime`` or
    as its text form, and the text form differs between PostgreSQL and
    SQLite.  Anything that is not an ISO-8601 timestamp yields None so the
    value falls through to the plain ``date`` validation, which reports the
    bad input in the usual way.

    Args:
        text: The string to try to read as a timestamp.

    Returns:
        The timestamp it carries, or None if it is not one.
    """
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


class DailyUserCount(BaseModel):
    """Schema for one day's user-creation count: a ``(date, count)`` pair.

    One of these is one entry of the JSON array served by the daily
    user-creation-counts endpoint (``GET /users/created-per-day``): the
    calendar day, and how many users were created on it.  A day on which no
    user was created is described the same way, with ``count`` of zero.

    Filling these from the database is TASK-D49B-002's job; exposing them over
    HTTP belongs to TASK-D49B-003 and TASK-D49B-004.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "date": "2026-07-09",
                    "count": 5,
                }
            ]
        }
    )

    date: DayType = Field(description="Calendar day the count describes, ISO 8601.")
    count: int = Field(description="Number of users created on that day.", ge=0)

    @field_validator("date", mode="before")
    @classmethod
    def reduce_to_calendar_day(cls, value: object) -> object:
        """Reduce a timestamp to the calendar day it falls on.

        The counts these entries describe come out of creation timestamps, so
        a timestamp is accepted for the day and reduced to the day it falls
        on — UTC for a timezone-aware one, as stamped for a naive one, whether
        it arrives as a ``datetime`` or as its ISO-8601 text.  A plain
        ``date``, or an ISO-8601 date string, needs no reducing and is passed
        to the regular field validation untouched.

        Args:
            value: The raw value supplied for the ``date`` field.

        Returns:
            The calendar day as a ``datetime.date``, or ``value`` unchanged.
        """
        if isinstance(value, datetime):
            return _calendar_day_of(value)
        if isinstance(value, str):
            moment = _timestamp_in(value)
            if moment is not None:
                return _calendar_day_of(moment)
        return value


class SingleDayUserCountResponse(DailyUserCount):
    """Schema for a user-creation count that covers exactly one day.

    It carries the same two fields as one :class:`DailyUserCount` entry, so a
    single-day response is also a valid entry of the multi-day array — which
    keeps the wire shape identical whichever way the count is asked for.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "date": "2026-07-09",
                    "count": 12,
                }
            ]
        }
    )
