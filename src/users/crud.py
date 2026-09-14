"""CRUD operations for User model."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import ColumnElement, and_, case, func, select
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


def _midnight(day: date) -> datetime:
    """Return midnight at the start of ``day`` as a naive datetime.

    Naive because ``users.created_at`` is a ``DateTime`` without a timezone, so
    a naive boundary compares like with like on both SQLite and PostgreSQL —
    the same approach ``count_users_today`` takes.

    Args:
        day: The calendar day to open.

    Returns:
        Midnight at the start of that day.
    """
    return datetime(day.year, day.month, day.day)


def _created_on_bucket(day: date) -> ColumnElement[int]:
    """Return the conditional aggregate counting users created on ``day``.

    One ``SUM(CASE WHEN ... THEN 1 ELSE 0 END)`` per day: the database does the
    counting, no date function is needed, and each day is described by the same
    half-open range as every other count in this module. Grouping by a SQL date
    function is the other option, but the two databases this project runs
    against disagree about which date functions exist and about the timezone a
    date is taken in (see the dialect detection in ``count_users_by_domain``),
    while ``created_at >= midnight AND created_at < next midnight`` is the same
    question in both.

    Args:
        day: The calendar day to count creations on.

    Returns:
        A SQL aggregate expression yielding that day's count.
    """
    return func.sum(
        case(
            (
                and_(
                    User.created_at >= _midnight(day),
                    User.created_at < _midnight(day + timedelta(days=1)),
                ),
                1,
            ),
            else_=0,
        )
    )


async def count_users_created_on_days(
    db: AsyncSession, window: Sequence[date]
) -> list[int]:
    """Count non-deleted users created on each day of ``window``, oldest first.

    ``window`` is a run of consecutive calendar days, oldest day first, and one
    count comes back per day in that same position — the caller never has to
    match rows back to days, and the order the days were asked for is the order
    they are answered in. Days with no creations are answered with 0 rather than
    left out: the aggregate carries no GROUP BY, so exactly one row comes back,
    holding NULL where nothing matched, which reads as a zero count.

    Users created outside the window — earlier than its first day, or stamped in
    the future — are counted nowhere, and soft-deleted users are excluded, as in
    ``count_users``, ``count_users_today`` and ``count_users_by_domain``.

    Args:
        db: The async database session.
        window: The calendar days to count over, oldest day first.

    Returns:
        One count per day of ``window``, in the order the days were given.

    Raises:
        ValueError: If ``window`` is empty, since then there is no question to
            put to the database.
        SQLAlchemyError: If the aggregate query fails.
    """
    if not window:
        raise ValueError(
            "count_users_created_on_days needs at least one day to count over"
        )

    buckets = [
        _created_on_bucket(day).label(f"day_{index}")
        for index, day in enumerate(window)
    ]
    stmt = (
        select(*buckets)
        .select_from(User)
        .where(User.created_at >= _midnight(window[0]))
        .where(User.created_at < _midnight(window[-1] + timedelta(days=1)))
        .where(User.deleted_at.is_(None))
    )
    result = await db.execute(stmt)

    return [int(count or 0) for count in result.one()]
