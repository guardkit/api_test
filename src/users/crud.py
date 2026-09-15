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
from src.users.models import User
from src.users.schemas import DailyCount, UserCreate, UserUpdate, to_iso_date

# How many days the daily-creation window spans when a caller does not say.
# One week: the analytics series is a week of days, current day last.
DAILY_COUNT_WINDOW_DAYS = 7


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
    rows = result.mappings().all()
    return [{"domain": row["domain"], "count": row["count"]} for row in rows]


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


def _start_of_day(day: date) -> datetime:
    """Return midnight at the start of a day, as a naive datetime.

    Naive on purpose: ``users.created_at`` is a timestamp without time zone
    (alembic revision a143501c5e1f), and a timezone-aware bound against that
    column is exactly what made ``/users/count-today`` answer 503 on
    PostgreSQL while SQLite shrugged it off. Day arithmetic therefore stays
    in the same terms the column is stored in.

    Args:
        day: The calendar day to place midnight on.

    Returns:
        Midnight at the start of ``day``.
    """
    return datetime(day.year, day.month, day.day)


def daily_count_aggregation_query(start: date, end: date) -> Select[Any]:
    """Build the query that aggregates user creations by calendar day.

    One row per calendar day that has at least one creation inside the closed
    range ``start``..``end``, each carrying the day and how many users were
    created on it, ordered oldest day first. Days inside the range with nothing
    to count produce no row — filling those in with a count of zero is the
    caller's job (TASK-A0AE-002 owns the seven-day window and its zero counts).

    ``date()`` is the one day-truncating expression both databases the app runs
    on accept spelled the same way: PostgreSQL reads it as a cast of the
    timestamp to ``date``, SQLite as its ``date()`` function. A
    ``CAST(... AS DATE)`` would not do: SQLite gives DATE numeric affinity and
    hands back the untouched timestamp text, silently counting every creation
    as its own day.

    Soft-deleted users are left out, as every other count in this module does.

    Args:
        start: The first calendar day to include, inclusive.
        end: The last calendar day to include, inclusive.

    Returns:
        A selectable statement with ``day`` and ``count`` columns, oldest day
        first.
    """
    day_expr = func.date(User.created_at)
    return (
        select(day_expr.label("day"), func.count().label("count"))
        .select_from(User)
        .where(User.created_at >= _start_of_day(start))
        .where(User.created_at < _start_of_day(end) + timedelta(days=1))
        .where(User.deleted_at.is_(None))
        .group_by(day_expr)
        .order_by(day_expr)
    )


async def get_daily_counts(
    db: AsyncSession, start: date, end: date
) -> list[DailyCount]:
    """Count how many users were created on each day of a date range.

    Args:
        db: The async database session.
        start: The first calendar day to include, inclusive.
        end: The last calendar day to include, inclusive.

    Returns:
        DailyCount data points for the days that have creations, ordered oldest
        to newest. Days with no creations are absent — see
        :func:`daily_count_aggregation_query`.
    """
    result = await db.execute(daily_count_aggregation_query(start, end))
    return [
        DailyCount(date=to_iso_date(row["day"]), count=row["count"])
        for row in result.mappings().all()
    ]


async def get_recent_daily_counts(
    db: AsyncSession,
    days: int = DAILY_COUNT_WINDOW_DAYS,
    today: date | None = None,
) -> list[DailyCount]:
    """Count user creations over the most recent window of calendar days.

    The window is the ``days`` consecutive days ending on the current day, and
    every one of them is reported: a day somebody registered on carries its
    count, a day nobody registered on carries zero. The series is therefore
    always exactly ``days`` long — an empty database answers with ``days`` days
    of zeros rather than with nothing — ordered oldest day first and the
    current day last.

    The current day is included even though it is not over yet, so its count is
    whatever has been created so far and grows as the day goes on. Nothing
    special is done to achieve that: the window ends at the start of tomorrow,
    which a partially elapsed day sits inside entirely.

    The day the window is measured from can be handed in, which keeps the
    window the same at 23:59 as at 00:01 and lets a caller re-ask about a day
    that has already closed.

    Args:
        db: The async database session.
        days: How many consecutive days the window spans, counting the current
            one. Defaults to :data:`DAILY_COUNT_WINDOW_DAYS`.
        today: The day to measure the window from. Defaults to the current UTC
            day, which is the day ``users.created_at`` is written in.

    Returns:
        Exactly ``days`` DailyCount data points, oldest to newest, with zero
        counts on the days that have no creations. Soft-deleted users are left
        out, as every other count in this module does.

    Raises:
        ValueError: When ``days`` is smaller than one, which describes no window
            at all.
    """
    if days < 1:
        raise ValueError(
            f"The daily-count window must span at least one day, got {days}."
        )

    anchor = datetime.now(UTC).date() if today is None else today
    start = anchor - timedelta(days=days - 1)

    result = await db.execute(daily_count_aggregation_query(start, anchor))
    counted = {
        to_iso_date(row["day"]): int(row["count"]) for row in result.mappings().all()
    }

    # The window's days, written the same way the rows above are keyed, so a day
    # matches whatever shape the database handed that day back in. A day the
    # aggregation did not mention had nothing to count, and reads zero.
    window = [to_iso_date(start + timedelta(days=step)) for step in range(days)]
    return [DailyCount(date=day, count=counted.get(day, 0)) for day in window]
