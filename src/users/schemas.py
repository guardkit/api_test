"""Pydantic schemas for users."""

from __future__ import annotations

from datetime import date as calendar_date
from datetime import datetime, timedelta

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


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


DEFAULT_USER_CREATION_WINDOW_DAYS: int = 7
"""How many days of creation history the analytics endpoint answers for."""


class UserCreationDayCount(BaseModel):
    """Schema for one day of user-creation analytics.

    A day with no creations is a day with a count of zero, not a missing entry.
    """

    date: calendar_date = Field(
        description="Calendar day the count belongs to, in UTC."
    )
    count: int = Field(ge=0, description="How many users were created that day.")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "date": "2026-07-02",
                    "count": 3,
                }
            ]
        }
    )


class UserCreationStats(BaseModel):
    """Response shape for user creations per day.

    The days are held oldest first and cover one window of consecutive days, so
    a reader can plot them straight away. ``total`` is derived from the days and
    cannot be set separately.
    """

    days: list[UserCreationDayCount] = Field(
        default_factory=list,
        description="Per-day creation counts, oldest day first.",
    )
    total: int = Field(
        default=0,
        ge=0,
        description="Derived: how many users the returned days account for.",
    )

    @model_validator(mode="after")
    def order_days_oldest_first(self) -> UserCreationStats:
        """Put the days in order, and refuse a response that repeats one.

        ``total`` is recomputed here rather than trusted, so a response cannot
        disagree with the days it carries.

        Raises:
            ValueError: When the same day appears more than once, which means the
                query behind the response grouped wrongly.

        Returns:
            UserCreationStats: The same stats, with its days ordered.
        """
        seen: set[calendar_date] = set()
        for day in self.days:
            if day.date in seen:
                raise ValueError(
                    f"day {day.date.isoformat()} appears twice in the response"
                )
            seen.add(day.date)
        self.days.sort(key=lambda day: day.date)
        self.total = sum(day.count for day in self.days)
        return self

    @classmethod
    def zero_filled_window(
        cls,
        start_day: calendar_date,
        window_days: int = DEFAULT_USER_CREATION_WINDOW_DAYS,
    ) -> UserCreationStats:
        """Build a window of consecutive days that all answer with zero.

        Serves the case where nothing was created: the window is still fully
        described, oldest day first.

        Args:
            start_day: The oldest day of the window.
            window_days: How many days the window spans.

        Returns:
            UserCreationStats: The zero-filled window.

        Raises:
            ValueError: When the window spans fewer than one day.
        """
        if window_days < 1:
            raise ValueError(f"window_days must be at least one, got {window_days}")

        return cls(
            days=[
                UserCreationDayCount(date=start_day + timedelta(days=offset), count=0)
                for offset in range(window_days)
            ]
        )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "days": [
                        {"date": "2026-07-02", "count": 3},
                        {"date": "2026-07-03", "count": 0},
                    ],
                    "total": 3,
                }
            ]
        }
    )
