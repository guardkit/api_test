"""Tests for user domain field in models and schemas."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import DeclarativeBase
from src.users.models import User
from src.users.schemas import UserCreate, UserPublic


class TestUserModelDomain:
    """Tests for the domain field on the User SQLAlchemy model."""

    @pytest.fixture(autouse=True)
    async def setup_database(self) -> None:
        """Set up an in-memory SQLite database for testing."""
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
        )

        async with self.engine.begin() as conn:
            await conn.run_sync(DeclarativeBase.metadata.create_all)

        self.async_session_factory: Any = sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @pytest.fixture
    async def async_session(self) -> AsyncSession:
        """Create an async session for testing."""
        async with self.async_session_factory() as session:
            yield session

    async def test_user_with_domain(self, async_session: AsyncSession) -> None:
        """Test creating a user with a domain field."""
        user = User(
            email="test@example.com",
            domain="example.com",
            full_name="Test User",
            is_active=True,
        )

        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.domain == "example.com"
        assert user.full_name == "Test User"

    async def test_user_without_domain(self, async_session: AsyncSession) -> None:
        """Test creating a user without a domain field (nullable)."""
        user = User(
            email="test@example.com",
            full_name="Test User",
        )

        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        assert user.domain is None

    async def test_user_domain_is_indexed(self) -> None:
        """Test that the domain column has an index."""
        mapper = User.__mapper__
        domain_column = mapper.columns.domain
        assert domain_column.index is True

    async def test_query_users_by_domain(
        self, async_session: AsyncSession
    ) -> None:
        """Test querying users by domain."""
        user1 = User(email="alice@example.com", domain="example.com")
        user2 = User(email="bob@other.com", domain="other.com")
        user3 = User(email="carol@example.com", domain="example.com")

        async_session.add_all([user1, user2, user3])
        await async_session.commit()

        result = await async_session.execute(
            select(User).where(User.domain == "example.com")
        )
        users = list(result.scalars().all())

        assert len(users) == 2
        domains = {u.domain for u in users}
        assert domains == {"example.com"}

    async def test_user_domain_nullable_in_database(
        self, async_session: AsyncSession
    ) -> None:
        """Test that domain can be null in the database."""
        user = User(email="test@example.com")
        async_session.add(user)
        await async_session.commit()
        await async_session.refresh(user)

        assert user.domain is None

    async def test_user_domain_unique_email_with_different_domains(
        self, async_session: AsyncSession
    ) -> None:
        """Test that users with different domains have unique emails."""
        user1 = User(email="alice@company.com", domain="company.com")
        user2 = User(email="alice@startup.com", domain="startup.com")

        async_session.add_all([user1, user2])
        await async_session.commit()

        result = await async_session.execute(select(User))
        users = list(result.scalars().all())

        assert len(users) == 2
        assert users[0].domain == "company.com"
        assert users[1].domain == "startup.com"


class TestUserCreateDomain:
    """Tests for domain field in UserCreate schema."""

    def test_user_create_domain_auto_populated(self) -> None:
        """Test that domain is automatically derived from email."""
        user = UserCreate(email="john.doe@example.com")

        assert user.email == "john.doe@example.com"
        assert user.domain == "example.com"

    def test_user_create_domain_case_insensitive(self) -> None:
        """Test that domain is lowercased from email."""
        user = UserCreate(email="USER@EXAMPLE.COM")

        assert user.domain == "example.com"

    def test_user_create_domain_with_subdomain(self) -> None:
        """Test domain extraction with subdomain."""
        user = UserCreate(email="user@sub.domain.com")

        assert user.domain == "sub.domain.com"

    def test_user_create_domain_explicitly_set(self) -> None:
        """Test that explicitly set domain is preserved."""
        user = UserCreate(email="user@example.com", domain="custom.com")

        assert user.domain == "custom.com"

    def test_user_create_domain_with_full_name(self) -> None:
        """Test domain with full_name provided."""
        user = UserCreate(
            email="john.doe@example.com",
            full_name="John Doe",
        )

        assert user.email == "john.doe@example.com"
        assert user.domain == "example.com"
        assert user.full_name == "John Doe"

    def test_user_create_invalid_email_raises(self) -> None:
        """Test that invalid email raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="not-an-email")

        assert "email" in str(exc_info.value)


class TestUserPublicDomain:
    """Tests for domain field in UserPublic schema."""

    def test_user_public_with_domain(self) -> None:
        """Test UserPublic with domain field."""
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "john.doe@example.com",
            "domain": "example.com",
            "full_name": "John Doe",
            "is_active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        user = UserPublic(**data)

        assert user.id == "550e8400-e29b-41d4-a716-446655440000"
        assert user.email == "john.doe@example.com"
        assert user.domain == "example.com"

    def test_user_public_without_domain(self) -> None:
        """Test UserPublic without domain field (nullable)."""
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "john.doe@example.com",
            "full_name": "John Doe",
            "is_active": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        user = UserPublic(**data)

        assert user.domain is None

    def test_user_public_from_attributes(self) -> None:
        """Test UserPublic from_attributes configuration."""
        assert UserPublic.model_config.get("from_attributes") is True
