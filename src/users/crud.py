"""CRUD operations for User model."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

from sqlalchemy import case, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.domain_extraction import extract_domains
from src.users.exceptions import (
    UserAlreadyExistsError,
    UserAlreadyInactiveError,
    UserNotFoundError,
)
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


async def deactivate_user(db: AsyncSession, user_id: str) -> User:
    """Set a live user's ``is_active`` flag to false.

    The check and the write are one statement: the ``UPDATE`` carries
    "still active and not deleted" in its own ``WHERE`` clause, so the row is
    claimed only if it is in the state the caller asked about. A read-then-write
    would let two concurrent callers both see an active user and both report
    success; here exactly one claim can match, and whoever loses the race is
    told the user was already inactive. Nothing is written when the claim does
    not match, which is what makes repeating the call safe.

    Args:
        db: The async database session.
        user_id: The ID of the user to deactivate.

    Returns:
        The deactivated User, reloaded from the database.

    Raises:
        UserNotFoundError: If no live user has that ID.
        UserAlreadyInactiveError: If the user exists but is already inactive,
            including when another caller deactivated it first.
        SQLAlchemyError: If the write fails; the session is rolled back first.
    """
    try:
        claim = cast(
            "CursorResult[tuple[Any, ...]]",
            await db.execute(
                update(User)
                .where(
                    User.id == user_id,
                    User.deleted_at.is_(None),
                    User.is_active.is_(True),
                )
                .values(is_active=False)
                # One guarded statement, with no session bookkeeping SELECT
                # around it. The returned object is reloaded below, so nothing
                # in this session is left reading the old flag.
                .execution_options(synchronize_session=False)
            ),
        )

        if claim.rowcount == 0:
            # Either there is no live user with that id, or another writer
            # claimed it first. Read past whatever this session already holds,
            # so the answer comes from the row and not from a stale object.
            current = (
                await db.execute(
                    select(User)
                    .where(User.id == user_id, User.deleted_at.is_(None))
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            if current is None:
                raise UserNotFoundError(user_id=user_id)
            raise UserAlreadyInactiveError(user_id=user_id)

        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise

    user = await get_user(db, user_id)
    if user is None:  # pragma: no cover - the claim just matched this row
        raise UserNotFoundError(user_id=user_id)

    await db.refresh(user)
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


async def get_active_user_counts(db: AsyncSession) -> dict[str, int]:
    """Count live users split by their ``is_active`` flag.

    Backs ``GET /users/active-count``. Soft-deleted users are excluded, the
    same way ``count_users`` excludes them, so ``active_count`` plus
    ``inactive_count`` equals the total that function returns.

    One round trip with one conditional aggregate per state: ``COUNT`` ignores
    the NULL that a non-matching ``CASE`` yields, so both counts come from a
    single scan and neither needs a ``COALESCE`` — ``COUNT`` is 0, never NULL,
    on an empty result set.

    Args:
        db: The async database session.

    Returns:
        Dict with 'active_count' and 'inactive_count' (both int), each 0 when
        no live users exist.
    """
    stmt = (
        select(
            func.count(case((User.is_active.is_(True), 1))).label("active_count"),
            func.count(case((User.is_active.is_(False), 1))).label("inactive_count"),
        )
        .select_from(User)
        .where(User.deleted_at.is_(None))
    )
    row = (await db.execute(stmt)).one()
    return {
        "active_count": int(row.active_count),
        "inactive_count": int(row.inactive_count),
    }


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


async def get_distinct_domains(db: AsyncSession) -> list[str]:
    """List the distinct email domains of the live users.

    The emails are read from the database and handed to the domain extraction
    utility, which is the project's one rule for what counts as a domain: an
    address with no usable domain part contributes nothing, and every domain
    that does contribute is lowercased, so ``User@Example.COM`` and
    ``user@example.com`` are one entry rather than two. Neither of those is
    something a ``DISTINCT`` over the column can say, which is why the rows
    come back to Python rather than being deduped in SQL.

    Soft-deleted users are excluded, as in every other read here.

    Args:
        db: The async database session.

    Returns:
        The distinct domains in alphabetical order. Empty when no live user
        has an address with a domain in it.
    """
    stmt = select(User.email).where(User.deleted_at.is_(None))
    result = await db.execute(stmt)
    emails = list(result.scalars().all())
    return sorted(set(extract_domains(emails)))


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
