"""Tests for user models."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import DeclarativeBase
from src.users.models import User


class TestUserModel:
    """Tests for User ORM model."""

    @pytest.fixture(autouse=True)
    async def setup_database(self) -> None:
        """Set up an in-memory SQLite database for testing."""
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
        )

        # Create all tables
        async with self.engine.begin() as conn:
            await conn.run_sync(DeclarativeBase.metadata.create_all)

        # Create session factory
        self.async_session_factory = sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @pytest.fixture
    async def async_session(self):
        """Create an async session for testing."""
        async with self.async_session_factory() as session:
            yield session

    async def test_user_creation(self, async_session: AsyncSession) -> None:
        """Test creating a user in the database."""
        user = User(
            email="test@example.com",
            full_name="Test User",
            is_active=True,
        )

        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.is_active is True
        assert user.created_at is not None
        assert user.updated_at is not None

    async def test_user_unique_email(self, async_session: AsyncSession) -> None:
        """Test that email is unique."""
        user1 = User(
            email="unique@example.com",
            full_name="User 1",
            is_active=True,
        )

        async_session.add(user1)
        await async_session.commit()

        # Try to create another user with the same email
        user2 = User(
            email="unique@example.com",
            full_name="User 2",
            is_active=True,
        )

        async_session.add(user2)

        with pytest.raises(Exception):
            await async_session.commit()

    async def test_user_default_values(self, async_session: AsyncSession) -> None:
        """Test that default values are applied correctly."""
        user = User(
            email="default@example.com",
            full_name=None,
        )

        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        assert user.is_active is True
        assert user.created_at is not None
        assert user.updated_at is not None

    async def test_user_update(self, async_session: AsyncSession) -> None:
        """Test updating a user."""
        user = User(
            email="update@example.com",
            full_name="Original Name",
            is_active=True,
        )

        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        original_created_at = user.created_at

        user.full_name = "Updated Name"
        user.is_active = False

        await async_session.commit()
        await async_session.refresh(user)

        assert user.full_name == "Updated Name"
        assert user.is_active is False
        # updated_at should be >= created_at after update
        # Note: SQLite's CURRENT_TIMESTAMP has second-level precision
        assert user.updated_at >= user.created_at
        assert user.created_at == original_created_at

    async def test_user_repr(self, async_session: AsyncSession) -> None:
        """Test the __repr__ method."""
        user = User(
            email="repr@example.com",
            full_name="Repr User",
        )

        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        repr_str = repr(user)
        assert "User" in repr_str
        assert user.id in repr_str
        assert "repr@example.com" in repr_str

    async def test_user_model_timestamps_auto_populated(self, async_session: AsyncSession) -> None:
        """Test that timestamps are auto-populated on creation."""
        user = User(
            email="timestamps@example.com",
            full_name="Timestamps User",
        )

        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        # created_at and updated_at should be set by the database
        assert user.created_at is not None
        assert user.updated_at is not None
        assert user.created_at == user.updated_at

    async def test_user_model_is_active_default(self, async_session: AsyncSession) -> None:
        """Test that is_active defaults to True."""
        user = User(
            email="default_active@example.com",
            full_name="Default Active User",
        )

        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        assert user.is_active is True


class TestUserModelIndex:
    """Tests for User model database indexes."""

    def test_user_email_index(self) -> None:
        """Test that email column has an index."""
        # Check the index exists in the table
        indexes = User.__table__.indexes
        index_names = [idx.name for idx in indexes]

        # There should be a unique index on email
        assert any("email" in name.lower() for name in index_names)

    def test_user_table_name(self) -> None:
        """Test that the table name is correct."""
        assert User.__tablename__ == "users"
