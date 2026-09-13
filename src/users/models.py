"""SQLAlchemy ORM model for users, and the analytics view over its timestamps."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Select, String, func, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import ColumnElement

from src.db.base import DeclarativeBase

if TYPE_CHECKING:
    pass


def creation_day_expression() -> ColumnElement[date]:
    """SQL expression giving the calendar day of a user's creation timestamp.

    Returns:
        ColumnElement[date]: An expression that works against SQLite and
        PostgreSQL alike, because both spell the day function ``date``.
    """
    return func.date(User.created_at)


def as_creation_day(value: object) -> date:
    """Read a creation day coming back from any supported database.

    SQLite hands back the ISO text the ``date()`` function produced, PostgreSQL
    hands back a ``date``, and a timezone-aware column would hand back a
    ``datetime``. All three mean the same thing here.

    Args:
        value: The value a database returned for a creation day.

    Returns:
        date: The calendar day the value names.

    Raises:
        ValueError: When the value is text that is not an ISO date.
        TypeError: When the value is not a day-shaped object at all.
    """
    if isinstance(value, datetime):
        return (
            value.astimezone(UTC).date() if value.tzinfo is not None else value.date()
        )
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"cannot read {value!r} as a creation day") from exc
    raise TypeError(
        f"cannot read {value!r} of type {type(value).__name__} as a creation day"
    )


class User(DeclarativeBase):
    """User model representing the users table in the database.

    Attributes:
        id: UUID primary key with server-default uuid4
        email: Unique, indexed string (not nullable)
        domain: Optional domain extracted from email, indexed
        full_name: Optional string
        is_active: Boolean, default True
        created_at: Timestamp, server-default now(), indexed for
            creation timestamp queries
        updated_at: Timestamp with timezone, server-default now(), onupdate now()
    """

    __tablename__ = "users"

    # Override the inherited id column to use Python-side UUID generation
    # This works with both SQLite and PostgreSQL
    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    email: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
        index=True,
    )
    domain: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
    )
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps - DeclarativeBase provides these, but we override to add timezone
    # created_at carries an index: creation analytics filter and group by it.
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email!r})"

    @hybrid_property
    def creation_day(self) -> date:
        """Calendar day on which this user was created.

        Aware timestamps are read in UTC; naive ones are taken as already UTC,
        which is how the column is written.
        """
        if self.created_at.tzinfo is not None:
            return self.created_at.astimezone(UTC).date()
        return self.created_at.date()

    @creation_day.inplace.expression
    @classmethod
    def _creation_day_expression(cls) -> ColumnElement[date]:
        """SQL form of :attr:`creation_day`, portable across dialects."""
        return creation_day_expression()

    @classmethod
    def created_between(
        cls,
        start: datetime,
        end: datetime,
        include_deleted: bool = False,
    ) -> Select[tuple[User]]:
        """Select the users created in the window from ``start`` to ``end``.

        The window is half-open: ``start`` is included, ``end`` is not, so two
        adjacent windows never count a user twice. Timestamps are compared as
        written on the column, which carries no timezone; pass naive UTC values.

        Args:
            start: Beginning of the window, included.
            end: End of the window, excluded.
            include_deleted: Whether soft-deleted users count as creations too.

        Returns:
            Select[tuple[User]]: A statement yielding the users in the window,
            oldest creation first.

        Raises:
            ValueError: When ``end`` does not fall after ``start``.
        """
        if end <= start:
            raise ValueError(
                f"creation window end {end.isoformat()} precedes its "
                f"start {start.isoformat()}"
            )

        stmt = select(cls).where(cls.created_at >= start, cls.created_at < end)
        if not include_deleted:
            stmt = stmt.where(cls.deleted_at.is_(None))
        return stmt.order_by(cls.created_at, cls.id)


class UserAnalytics:
    """Creation timestamp analytics over the users table.

    This maps no table of its own. It is the analytics face of the ``User``
    model: every statement it builds selects, filters and groups the columns the
    ``User`` model declares, so a creation timestamp query has one home rather
    than one per caller.
    """

    @staticmethod
    def creation_day(user: User) -> date:
        """Return the calendar day on which ``user`` was created.

        Args:
            user: The user whose creation timestamp is being read.

        Returns:
            date: The creation day, UTC.
        """
        return user.creation_day

    @staticmethod
    def daily_count_statement(start_day: date, end_day: date) -> Select[Any]:
        """Build the per-day creation count for an inclusive window of days.

        Args:
            start_day: First day of the window.
            end_day: Last day of the window.

        Returns:
            Select[Any]: A statement of ``(creation_day, user_count)`` rows,
            oldest day first. Days without a creation return no row; callers
            that must answer for every day fill the gaps themselves.

        Raises:
            ValueError: When ``end_day`` precedes ``start_day``.
        """
        if end_day < start_day:
            raise ValueError(
                f"creation window end {end_day.isoformat()} precedes its "
                f"start {start_day.isoformat()}"
            )

        window_start = datetime.combine(start_day, time.min)
        window_end = datetime.combine(end_day + timedelta(days=1), time.min)
        creation_day = creation_day_expression()

        return (
            select(
                creation_day.label("creation_day"),
                func.count(User.id).label("user_count"),
            )
            .where(User.created_at >= window_start)
            .where(User.created_at < window_end)
            .where(User.deleted_at.is_(None))
            .group_by(creation_day)
            .order_by(creation_day)
        )

    @staticmethod
    def daily_counts(rows: Sequence[Any]) -> list[tuple[date, int]]:
        """Read query rows as ``(day, count)`` pairs, oldest day first.

        Args:
            rows: Rows of ``(day, count)`` as a database returned them.

        Returns:
            list[tuple[date, int]]: The rows, normalised and ordered.

        Raises:
            ValueError: When a row is not a day-and-count pair, or its day
                cannot be read as a date.
            TypeError: When a row's day is not a date-shaped value at all.
        """
        counts: list[tuple[date, int]] = []
        for row in rows:
            values = tuple(row)
            if len(values) != 2:
                raise ValueError(f"expected a day and a count, got {values!r}")
            counts.append((as_creation_day(values[0]), int(values[1])))
        counts.sort(key=lambda day_and_count: day_and_count[0])
        return counts
