"""CRUD operations for User model."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.exceptions import UserAlreadyExistsError
from src.users.models import User, UserAnalytics, creation_day_expression
from src.users.schemas import (
    DEFAULT_USER_CREATION_WINDOW_DAYS,
    UserCreate,
    UserCreationDayCount,
    UserCreationStats,
    UserUpdate,
)


async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    """Create a new user.

    Args:
        db: The async database session.
        user_in: User creation data.

    Returns:
        The created User object.

    Raises:
        UserAlreadyExistsError: If a user with the same email already exists.
    """
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        domain=user_in.domain,
        is_active=True,
    )

    db.add(user)
    try:
        await db.flush()
        await db.refresh(user)
        await db.commit()
        return user
    except IntegrityError:
        await db.rollback()
        raise UserAlreadyExistsError(email=user_in.email) from None


async def get_user(db: AsyncSession, user_id: str) -> User | None:
    """Get a user by ID.

    Args:
        db: The async database session.
        user_id: The UUID of the user.

    Returns:
        The User object if found, None otherwise.
    """
    stmt = select(User).where(User.id == user_id).where(User.deleted_at.is_(None))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_users(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> Sequence[User]:
    """Get a list of users with optional pagination.

    Args:
        db: The async database session.
        skip: Number of records to skip (default 0).
        limit: Maximum number of records to return (default 100).

    Returns:
        Sequence of User objects.
    """
    stmt = select(User).where(User.deleted_at.is_(None)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Get a user by email.

    Args:
        db: The async database session.
        email: The email address to search for.

    Returns:
        The User object if found, None otherwise.
    """
    stmt = select(User).where(User.email == email).where(User.deleted_at.is_(None))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_user(
    db: AsyncSession, user_id: str, user_in: UserUpdate
) -> User | None:
    """Update an existing user with partial data.

    Args:
        db: The async database session.
        user_id: The UUID of the user to update.
        user_in: User update data (only provided fields will be updated).

    Returns:
        The updated User object if found, None if user not found.
    """
    user = await get_user(db, user_id)
    if user is None:
        return None

    # Update only the fields that were explicitly set
    update_data = user_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    db.add(user)
    await db.flush()
    await db.refresh(user)
    await db.commit()
    return user


async def delete_user(db: AsyncSession, user_id: str) -> bool:
    """Soft-delete a user by ID.

    Sets the ``deleted_at`` timestamp instead of removing the row,
    so that count endpoints can exclude deleted users while preserving
    audit history.

    Returns False if the user is already soft-deleted (prevents double-delete).

    Args:
        db: The async database session.
        user_id: The UUID of the user to delete.

    Returns:
        True if the user was deleted, False if not found or already deleted.
    """
    user = await get_user(db, user_id)
    if user is None:
        return False

    # Prevent double-delete: if already soft-deleted, return False
    if user.deleted_at is not None:
        return False

    user.deleted_at = datetime.now(UTC)
    db.add(user)
    try:
        await db.flush()
        await db.commit()
        return True
    except SQLAlchemyError:
        await db.rollback()
        logger = logging.getLogger(__name__)
        logger.exception("Database error while deleting user %s", user_id)
        raise


async def count_users(db: AsyncSession) -> int:
    """Count total number of non-deleted users.

    Args:
        db: The async database session.

    Returns:
        Total number of non-deleted users in the database.
    """
    stmt = select(func.count()).select_from(User).where(User.deleted_at.is_(None))
    result = await db.execute(stmt)
    return result.scalar_one() or 0


async def count_users_today(db: AsyncSession) -> int:
    """Count users created on the current day.

    Uses date-only comparison so that users created at any time
    during the current calendar day are included.

    Args:
        db: The async database session.

    Returns:
        Number of users created today.
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Build start-of-today and start-of-tomorrow as naive datetimes
    # to match the naive DateTime column type used by the User model.
    start_today = datetime(today.year, today.month, today.day)
    start_tomorrow = datetime(tomorrow.year, tomorrow.month, tomorrow.day)

    stmt = (
        select(func.count())
        .select_from(User)
        .where(User.created_at >= start_today)
        .where(User.created_at < start_tomorrow)
        .where(User.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    return result.scalar_one() or 0


async def count_users_by_domain(
    db: AsyncSession, min_count: int | None = None
) -> list[dict[str, int | str]]:
    """Count users grouped by email domain.

    Extracts the domain portion from each user's email address, groups by domain,
    and returns counts ordered by count descending.

    Uses a SQL expression that works across both SQLite and PostgreSQL:
    - SQLite: INSTR(email, '@') to find the @ position
    - PostgreSQL: POSITION('@' IN email) via SQLAlchemy's func.position

    Malformed emails (those without '@') are excluded from the count.

    When ``min_count`` is provided, only domains with a count >= min_count
    are included in the result.

    Args:
        db: The async database session.
        min_count: Optional minimum count threshold for filtering domains.

    Returns:
        List of dicts with 'domain' (str) and 'count' (int) keys,
        ordered by count descending.
    """
    # Postgres has no instr(); SQLite has no strpos(). The sandbox gate
    # caught this live on 2026-08-25: green on the SQLite test database,
    # 503 on the real Postgres. Pick the position function by dialect —
    # what the old comment claimed and never did.
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "postgresql":
        at_position = func.strpos(User.email, "@")
    else:
        at_position = func.instr(User.email, "@")

    domain_expr = func.substr(
        User.email,
        at_position + 1,
    )

    count_expr = func.count().label("count")
    stmt = (
        select(domain_expr.label("domain"), count_expr)
        .select_from(User)
        .where(at_position > 0)
        .where(User.deleted_at.is_(None))
        .group_by(domain_expr)
        .order_by(func.count().desc())
    )

    if min_count is not None:
        stmt = stmt.having(func.count() >= min_count)

    result = await db.execute(stmt)
    rows = result.fetchall()
    # Read the columns by position: ``Row`` derives from ``tuple``, so the
    # attribute ``row.count`` resolves to ``tuple.count`` rather than to the
    # labelled count column, which mypy (strict) rightly refused.
    return [{"domain": str(row[0]), "count": int(row[1])} for row in rows]


async def get_recent_users(db: AsyncSession, limit: int = 10) -> Sequence[User]:
    """Get the most recently created users in descending order.

    Args:
        db: The async database session.
        limit: Maximum number of users to return (default 10).

    Returns:
        Sequence of User objects ordered by created_at descending.
    """
    stmt = select(User).order_by(User.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


def users_created_between_statement(
    start: datetime,
    end: datetime,
    include_deleted: bool = False,
) -> Select[tuple[User]]:
    """Build the query for the users created in a window of timestamps.

    The window is half-open: ``start`` is included, ``end`` is not, so two
    adjacent windows never count a user twice. Pass naive UTC timestamps, which
    is how the ``created_at`` column is written.

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
    stmt = (
        select(User)
        .where(User.created_in_window(start, end, include_deleted=include_deleted))
        .order_by(User.created_at, User.id)
    )
    return stmt


def users_created_per_day_statement(start_day: date, end_day: date) -> Select[Any]:
    """Build the per-day creation count for an inclusive window of days.

    Args:
        start_day: First day of the window.
        end_day: Last day of the window.

    Returns:
        Select[Any]: A statement of ``(creation_day, user_count)`` rows, oldest
        day first. Days without a creation return no row; callers that must
        answer for every day fill the gaps themselves.

    Raises:
        ValueError: When ``end_day`` precedes ``start_day``.
    """
    window_start, window_end = UserAnalytics.daily_count_window(start_day, end_day)
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


async def get_users_created_per_day(
    db: AsyncSession,
    *,
    window_days: int = DEFAULT_USER_CREATION_WINDOW_DAYS,
    end_day: date | None = None,
) -> UserCreationStats:
    """Count the users created on each day of the recent creation window.

    The window ends on ``end_day`` — on today when no day is named — and runs
    ``window_days`` days back, the last day included. Every day of the window is
    answered for: a day without a creation carries a count of zero rather than
    going missing, so the response reads as one unbroken run of days, oldest
    first.

    Days are read from ``created_at``, which the model writes as naive UTC, and
    grouped by the calendar day expression the model layer declares, so SQLite
    and PostgreSQL answer the same way. Soft-deleted users are not counted as
    creations, as every other count here agrees.

    Args:
        db: The async database session.
        window_days: How many consecutive days the answer covers, today's day
            included. Defaults to the window the schema declares.
        end_day: The newest day of the window, defaulting to today. Name it to
            ask about a window that has already closed.

    Returns:
        UserCreationStats: One entry per day of the window, oldest day first,
        and the total the days account for.

    Raises:
        ValueError: When the window spans fewer than one day.
        sqlalchemy.exc.SQLAlchemyError: When the database refused the count; the
            failure is logged with the window that was asked for, then raised.
    """
    if window_days < 1:
        raise ValueError(f"window_days must be at least one, got {window_days}")

    last_day = date.today() if end_day is None else end_day
    first_day = last_day - timedelta(days=window_days - 1)

    try:
        result = await db.execute(users_created_per_day_statement(first_day, last_day))
    except SQLAlchemyError:
        logger = logging.getLogger(__name__)
        logger.exception(
            "Database error while counting user creations from %s through %s",
            first_day,
            last_day,
        )
        raise

    counts = dict(UserAnalytics.daily_counts(result.all()))
    window = [first_day + timedelta(days=offset) for offset in range(window_days)]

    return UserCreationStats(
        days=[
            UserCreationDayCount(date=day, count=counts.get(day, 0)) for day in window
        ]
    )
