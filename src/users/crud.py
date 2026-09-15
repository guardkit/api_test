"""CRUD operations for User model."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.exceptions import UserAlreadyExistsError
from src.users.models import User
from src.users.schemas import UserCreate, UserUpdate


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
    return [{"domain": row.domain, "count": row.count} for row in rows]


def _as_calendar_date(value: object) -> date:
    """Coerce a grouped day expression into a calendar date.

    ``date(timestamp)`` comes back differently per driver: a ``date`` on
    PostgreSQL, a full ``datetime`` on some drivers, and a ``YYYY-MM-DD``
    string on SQLite (which stores datetimes as text).

    Args:
        value: The raw value of the grouped day expression.

    Returns:
        The calendar date the expression refers to.

    Raises:
        ValueError: If the value is not a recognisable date.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError as exc:
            raise ValueError(
                f"Unexpected day value from database: {value!r} is not an ISO-8601 date"
            ) from exc
    raise ValueError(f"Unexpected day value from database: {value!r}")


async def count_users_created_per_day(
    db: AsyncSession, days: int = 7
) -> list[dict[str, str | int]]:
    """Count users created on each of the last ``days`` days, oldest first.

    The window ends with the current calendar day and covers ``days`` days
    in total, so the default window is today plus the six days before it.
    Days with no creations are included with a count of zero, so the result
    always holds exactly ``days`` entries.

    Soft-deleted users are excluded, matching the other count functions.
    Naive datetime bounds are used to match the naive DateTime column of
    the User model (see ``count_users_today``).

    Args:
        db: The async database session.
        days: Size of the window in days, including today. Must be >= 1.

    Returns:
        List of ``days`` dicts with 'date' (ISO-8601 str) and 'count' (int)
        keys, ordered from the oldest day to the newest.

    Raises:
        ValueError: If ``days`` is smaller than one.
    """
    if days < 1:
        raise ValueError(f"days must be at least 1, got {days}")

    today = date.today()
    start_day = today - timedelta(days=days - 1)

    window_start = datetime(start_day.year, start_day.month, start_day.day)
    window_end = datetime(today.year, today.month, today.day) + timedelta(days=1)

    # date() truncates a timestamp to its calendar day and exists on both
    # SQLite and PostgreSQL; the dialect-specific helpers used by
    # count_users_by_domain are only needed where no common function exists.
    # The label is deliberately not "count": Row exposes a `count` attribute,
    # so `row.count` would not be the column.
    day_expr = func.date(User.created_at)
    stmt = (
        select(day_expr.label("day"), func.count().label("day_count"))
        .select_from(User)
        .where(User.created_at >= window_start)
        .where(User.created_at < window_end)
        .where(User.deleted_at.is_(None))
        .group_by(day_expr)
    )
    result = await db.execute(stmt)

    counts: dict[date, int] = {}
    for row in result.fetchall():
        counts[_as_calendar_date(row.day)] = int(row.day_count)

    return [
        {
            "date": (start_day + timedelta(days=offset)).isoformat(),
            "count": counts.get(start_day + timedelta(days=offset), 0),
        }
        for offset in range(days)
    ]


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
