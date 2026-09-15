"""Pydantic schemas for users."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

# What a daily-count day may be handed over as: the ``datetime.date`` PostgreSQL
# gives back for a day expression, the ``YYYY-MM-DD`` text SQLite gives back for
# the same expression, an ordinary ``datetime``, or the ISO8601 string the
# schema itself declares. ``to_iso_date`` turns any of them into that last one.
# Named at module scope because inside a model body ``date`` is the field, not
# the type.
DayValue: TypeAlias = date | datetime | str


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


def to_iso_date(value: DayValue) -> str:
    """Normalize a day to the ISO8601 date string the daily-count schemas declare.

    Why the input can be three things: the daily-count aggregation reads the day
    straight out of the database, and the two databases the app runs on do not
    hand back the same Python type for it. PostgreSQL's ``date`` column
    expression arrives as a ``datetime.date``; SQLite's arrives as the
    ``YYYY-MM-DD`` text its ``date()`` produces. A caller holding a
    ``datetime`` is a third way in.

    A timezone-aware datetime is placed into UTC first, so a creation recorded
    late in a day east of UTC lands on the UTC day the service reports.

    Args:
        value: The day to normalize.

    Returns:
        The day as an ISO8601 calendar-date string, ``YYYY-MM-DD``.

    Raises:
        ValueError: When a string is not a valid ISO8601 date or datetime.
    """
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(UTC)
        return value.date().isoformat()
    return value.isoformat()


class DailyCount(BaseModel):
    """Schema for one data point of the daily user-creation analytics.

    A data point is a single calendar day and the number of users created on
    it; a series of these, oldest day first, is what the analytics endpoint
    returns.
    """

    date: str
    count: int

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "date": "2026-07-08",
                    "count": 5,
                }
            ]
        }
    )

    @field_validator("date", mode="before")
    @classmethod
    def format_date(cls, value: DayValue) -> str:
        """Normalize the day to an ISO8601 date string.

        Args:
            value: The day as a date, a datetime, or an ISO8601 string.

        Returns:
            The day as an ISO8601 date string.

        Raises:
            ValueError: When the value is not a recognisable ISO8601 day.
        """
        return to_iso_date(value)


class DailyCountResponse(BaseModel):
    """Schema for a daily user-creation count entry.

    Carries the same two fields as a :class:`DailyCount` data point, in the
    same shape ``DomainCountResponse`` uses for its entries, so a handler can
    return one of these on its own or a list of them as the seven-day series.
    """

    date: str
    count: int

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "date": "2026-07-08",
                    "count": 5,
                }
            ]
        }
    )

    @field_validator("date", mode="before")
    @classmethod
    def format_date(cls, value: DayValue) -> str:
        """Normalize the day to an ISO8601 date string.

        Args:
            value: The day as a date, a datetime, or an ISO8601 string.

        Returns:
            The day as an ISO8601 date string.

        Raises:
            ValueError: When the value is not a recognisable ISO8601 day.
        """
        return to_iso_date(value)


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
