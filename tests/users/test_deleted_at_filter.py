"""Tests for deleted_at filtering in user CRUD operations.

Covers AC-001 (get_user filters deleted), AC-002 (list_users/get_users
filters deleted), and AC-003 (count_users_by_domain filters deleted).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate


class TestGetUserDeletedAtFilter:
    """AC-001: get_user filters out users with deleted_at set."""

    async def test_get_user_returns_active_user(
        self, db_session: AsyncSession
    ) -> None:
        """Active (non-deleted) users should be returned."""
        user_in = UserCreate(email="active@example.com", full_name="Active")
        user = await crud.create_user(db_session, user_in)

        result = await crud.get_user(db_session, user.id)

        assert result is not None
        assert result.id == user.id
        assert result.deleted_at is None

    async def test_get_user_returns_none_for_deleted_user(
        self, db_session: AsyncSession
    ) -> None:
        """Soft-deleted users should not be returned by get_user."""
        user_in = UserCreate(email="deleted@example.com", full_name="Deleted")
        user = await crud.create_user(db_session, user_in)

        # Soft-delete the user
        user.deleted_at = datetime.now(UTC)
        db_session.add(user)
        await db_session.flush()

        result = await crud.get_user(db_session, user.id)

        assert result is None

    async def test_get_user_mixed_deleted_and_active(
        self, db_session: AsyncSession
    ) -> None:
        """Only active users should be returned when some are deleted."""
        active_in = UserCreate(email="active@example.com", full_name="Active")
        active_user = await crud.create_user(db_session, active_in)

        deleted_in = UserCreate(email="deleted@example.com", full_name="Deleted")
        deleted_user = await crud.create_user(db_session, deleted_in)

        # Soft-delete one user
        deleted_user.deleted_at = datetime.now(UTC)
        db_session.add(deleted_user)
        await db_session.flush()

        # Active user should be found
        result_active = await crud.get_user(db_session, active_user.id)
        assert result_active is not None
        assert result_active.email == "active@example.com"

        # Deleted user should not be found
        result_deleted = await crud.get_user(db_session, deleted_user.id)
        assert result_deleted is None


class TestGetUsersDeletedAtFilter:
    """AC-002: list_users (get_users) filters out users with deleted_at set."""

    async def test_get_users_excludes_deleted(
        self, db_session: AsyncSession
    ) -> None:
        """Deleted users should not appear in get_users results."""
        # Create 3 active users
        for i in range(3):
            await crud.create_user(
                db_session,
                UserCreate(email=f"user{i}@example.com", full_name=f"User {i}"),
            )

        # Create and soft-delete 2 users
        for i in range(2):
            user_in = UserCreate(
                email=f"deleted{i}@example.com", full_name=f"Deleted {i}"
            )
            user = await crud.create_user(db_session, user_in)
            user.deleted_at = datetime.now(UTC)
            db_session.add(user)
        await db_session.flush()

        users = await crud.get_users(db_session)

        assert len(users) == 3
        for user in users:
            assert user.deleted_at is None

    async def test_get_users_empty_when_all_deleted(
        self, db_session: AsyncSession
    ) -> None:
        """get_users returns empty list when all users are deleted."""
        user_in = UserCreate(email="single@example.com", full_name="Single")
        user = await crud.create_user(db_session, user_in)

        user.deleted_at = datetime.now(UTC)
        db_session.add(user)
        await db_session.flush()

        users = await crud.get_users(db_session)

        assert users == []

    async def test_get_users_pagination_respects_deleted_filter(
        self, db_session: AsyncSession
    ) -> None:
        """Pagination in get_users should only count active users."""
        # Create 5 active users
        for i in range(5):
            await crud.create_user(
                db_session,
                UserCreate(
                    email=f"active{i}@example.com", full_name=f"Active {i}"
                ),
            )

        # Create and soft-delete 3 users
        for i in range(3):
            user_in = UserCreate(
                email=f"deleted{i}@example.com", full_name=f"Deleted {i}"
            )
            user = await crud.create_user(db_session, user_in)
            user.deleted_at = datetime.now(UTC)
            db_session.add(user)
        await db_session.flush()

        users = await crud.get_users(db_session, skip=0, limit=3)

        assert len(users) == 3
        for user in users:
            assert user.deleted_at is None


class TestCountUsersByDomainDeletedAtFilter:
    """AC-003: count_users_by_domain filters out deleted users."""

    async def test_count_by_domain_excludes_deleted(
        self, db_session: AsyncSession
    ) -> None:
        """Deleted users should not be counted in domain counts."""
        # 2 active users from example.com
        for i in range(2):
            await crud.create_user(
                db_session,
                UserCreate(email=f"active{i}@example.com", full_name=f"Active {i}"),
            )

        # 2 deleted users from example.com
        for i in range(2):
            user_in = UserCreate(
                email=f"deleted{i}@example.com", full_name=f"Deleted {i}"
            )
            user = await crud.create_user(db_session, user_in)
            user.deleted_at = datetime.now(UTC)
            db_session.add(user)
        await db_session.flush()

        result = await crud.count_users_by_domain(db_session)

        assert len(result) == 1
        assert result[0]["domain"] == "example.com"
        assert result[0]["count"] == 2  # Only active users counted

    async def test_count_by_domain_empty_when_all_deleted(
        self, db_session: AsyncSession
    ) -> None:
        """count_users_by_domain returns empty list when all users are deleted."""
        user_in = UserCreate(email="single@example.com", full_name="Single")
        user = await crud.create_user(db_session, user_in)

        user.deleted_at = datetime.now(UTC)
        db_session.add(user)
        await db_session.flush()

        result = await crud.count_users_by_domain(db_session)

        assert result == []
