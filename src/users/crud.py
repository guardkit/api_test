"""CRUD operations for User model."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.exceptions import UserAlreadyExistsError, UserNotFoundError
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
        is_active=True,
    )

    db.add(user)
    try:
        await db.flush()
        await db.refresh(user)
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
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> Sequence[User]:
    """Get a list of users with optional pagination.

    Args:
        db: The async database session.
        skip: Number of records to skip (default 0).
        limit: Maximum number of records to return (default 100).

    Returns:
        Sequence of User objects.
    """
    stmt = select(User).offset(skip).limit(limit)
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
    stmt = select(User).where(User.email == email)
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
    return user


async def delete_user(db: AsyncSession, user_id: str) -> bool:
    """Delete a user by ID.

    Args:
        db: The async database session.
        user_id: The UUID of the user to delete.

    Returns:
        True if the user was deleted, False if not found.
    """
    user = await get_user(db, user_id)
    if user is None:
        return False

    await db.delete(user)
    await db.flush()
    return True


async def count_users(db: AsyncSession) -> int:
    """Count total number of users.

    Args:
        db: The async database session.

    Returns:
        Total number of users in the database.
    """
    stmt = select(select(func.count()).select_from(User).scalar_subquery())
    result = await db.execute(stmt)
    return result.scalar_one_or_none() or 0
