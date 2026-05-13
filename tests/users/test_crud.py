"""Tests for CRUD operations on User model."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.exceptions import UserAlreadyExistsError, UserNotFoundError
from src.users.models import User
from src.users.schemas import UserCreate, UserUpdate


class TestCreateUser:
    """Tests for create_user function."""

    async def test_create_user_success(self, db_session: AsyncSession) -> None:
        """Test successful user creation."""
        user_in = UserCreate(
            email="test@example.com",
            full_name="Test User",
        )

        user = await crud.create_user(db_session, user_in)

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.is_active is True

    async def test_create_user_duplicate_email(
        self, db_session: AsyncSession
    ) -> None:
        """Test that duplicate email raises UserAlreadyExistsError."""
        user_in = UserCreate(
            email="duplicate@example.com",
            full_name="First User",
        )

        # Create first user
        await crud.create_user(db_session, user_in)

        # Try to create second user with same email
        user_in2 = UserCreate(
            email="duplicate@example.com",
            full_name="Second User",
        )

        with pytest.raises(UserAlreadyExistsError):
            await crud.create_user(db_session, user_in2)

    async def test_create_user_minimal(self, db_session: AsyncSession) -> None:
        """Test user creation with only required field."""
        user_in = UserCreate(email="minimal@example.com")

        user = await crud.create_user(db_session, user_in)

        assert user.id is not None
        assert user.email == "minimal@example.com"
        assert user.full_name is None


class TestGetUser:
    """Tests for get_user function."""

    async def test_get_user_found(self, db_session: AsyncSession) -> None:
        """Test getting an existing user."""
        # Create a user first
        user_in = UserCreate(email="get@example.com", full_name="Get User")
        created = await crud.create_user(db_session, user_in)

        user = await crud.get_user(db_session, created.id)

        assert user is not None
        assert user.id == created.id
        assert user.email == "get@example.com"

    async def test_get_user_not_found(self, db_session: AsyncSession) -> None:
        """Test getting a non-existent user."""
        user = await crud.get_user(db_session, "non-existent-id")

        assert user is None


class TestGetUsers:
    """Tests for get_users function."""

    async def test_get_users_empty(self, db_session: AsyncSession) -> None:
        """Test getting users when database is empty."""
        users = await crud.get_users(db_session)

        assert users == []

    async def test_get_users_with_data(self, db_session: AsyncSession) -> None:
        """Test getting users with existing data."""
        # Create multiple users
        for i in range(5):
            await crud.create_user(
                db_session,
                UserCreate(email=f"user{i}@example.com", full_name=f"User {i}"),
            )

        users = await crud.get_users(db_session)

        assert len(users) == 5

    async def test_get_users_pagination(self, db_session: AsyncSession) -> None:
        """Test getting users with pagination."""
        # Create multiple users
        for i in range(10):
            await crud.create_user(
                db_session,
                UserCreate(email=f"user{i}@example.com", full_name=f"User {i}"),
            )

        # Test skip
        users_skip = await crud.get_users(db_session, skip=5)
        assert len(users_skip) == 5

        # Test limit
        users_limit = await crud.get_users(db_session, limit=3)
        assert len(users_limit) == 3

        # Test both
        users_both = await crud.get_users(db_session, skip=2, limit=3)
        assert len(users_both) == 3


class TestGetUserByEmail:
    """Tests for get_user_by_email function."""

    async def test_get_user_by_email_found(
        self, db_session: AsyncSession
    ) -> None:
        """Test getting a user by email."""
        user_in = UserCreate(email="email@example.com", full_name="Email User")
        await crud.create_user(db_session, user_in)

        user = await crud.get_user_by_email(db_session, "email@example.com")

        assert user is not None
        assert user.email == "email@example.com"

    async def test_get_user_by_email_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """Test getting a non-existent user by email."""
        user = await crud.get_user_by_email(db_session, "nonexistent@example.com")

        assert user is None


class TestUpdateUser:
    """Tests for update_user function."""

    async def test_update_user_found(self, db_session: AsyncSession) -> None:
        """Test updating an existing user."""
        user_in = UserCreate(
            email="update@example.com", full_name="Original Name"
        )
        created = await crud.create_user(db_session, user_in)

        update_in = UserUpdate(full_name="Updated Name")
        user = await crud.update_user(db_session, created.id, update_in)

        assert user is not None
        assert user.full_name == "Updated Name"
        assert user.email == "update@example.com"  # Unchanged

    async def test_update_user_partial(self, db_session: AsyncSession) -> None:
        """Test that update uses exclude_unset=True."""
        user_in = UserCreate(
            email="partial@example.com", full_name="Original Name"
        )
        created = await crud.create_user(db_session, user_in)

        # Update only is_active, leave full_name alone
        update_in = UserUpdate(is_active=False)
        user = await crud.update_user(db_session, created.id, update_in)

        assert user is not None
        assert user.is_active is False
        assert user.full_name == "Original Name"  # Unchanged

    async def test_update_user_not_found(self, db_session: AsyncSession) -> None:
        """Test updating a non-existent user."""
        user = await crud.update_user(
            db_session, "non-existent-id", UserUpdate(full_name="New Name")
        )

        assert user is None


class TestDeleteUser:
    """Tests for delete_user function."""

    async def test_delete_user_found(self, db_session: AsyncSession) -> None:
        """Test deleting an existing user."""
        user_in = UserCreate(email="delete@example.com", full_name="Delete User")
        created = await crud.create_user(db_session, user_in)

        result = await crud.delete_user(db_session, created.id)

        assert result is True

        # Verify user is deleted
        user = await crud.get_user(db_session, created.id)
        assert user is None

    async def test_delete_user_not_found(self, db_session: AsyncSession) -> None:
        """Test deleting a non-existent user."""
        result = await crud.delete_user(db_session, "non-existent-id")

        assert result is False


class TestCountUsers:
    """Tests for count_users function."""

    async def test_count_users_empty(self, db_session: AsyncSession) -> None:
        """Test counting users when database is empty."""
        count = await crud.count_users(db_session)

        assert count == 0

    async def test_count_users_with_data(self, db_session: AsyncSession) -> None:
        """Test counting users with existing data."""
        # Create multiple users
        for i in range(5):
            await crud.create_user(
                db_session,
                UserCreate(email=f"count{i}@example.com", full_name=f"Count {i}"),
            )

        count = await crud.count_users(db_session)

        assert count == 5
