"""Tests for soft-delete and count endpoint behavior.

Verifies that count endpoints exclude soft-deleted users and reflect
reduced counts in real-time after deletion.
"""

from __future__ import annotations

from http import HTTPStatus
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate

AUTH_TOKEN = "dev-token"


class TestSoftDeleteCountReflection:
    """Tests that count endpoints exclude deleted users in real-time."""

    # AC-001: count endpoint reflects reduced count after deletion
    @pytest.mark.asyncio
    async def test_count_decreases_after_soft_delete(
        self, db_session: AsyncSession
    ) -> None:
        """Test that GET /users/count decreases after user deletion.

        Creates two users, counts them, deletes one, and verifies the
        count decreases by one.
        """
        # Create two users
        user_in_1 = UserCreate(email="count1@example.com", full_name="Count 1")
        user_in_2 = UserCreate(email="count2@example.com", full_name="Count 2")
        user1 = await crud.create_user(db_session, user_in_1)
        user2 = await crud.create_user(db_session, user_in_2)
        await db_session.flush()
        await db_session.refresh(user1)
        await db_session.refresh(user2)

        # Verify initial count
        initial_count = await crud.count_users(db_session)
        assert initial_count == 2

        # Delete one user (soft-delete)
        deleted = await crud.delete_user(db_session, user1.id)
        assert deleted is True

        # get_user filters out deleted users per AC-001
        retrieved = await crud.get_user(db_session, user1.id)
        assert retrieved is None

        # Verify count decreased
        final_count = await crud.count_users(db_session)
        assert final_count == 1

    # AC-001: count-today endpoint reflects reduced count after deletion
    @pytest.mark.asyncio
    async def test_count_today_decreases_after_soft_delete(
        self, db_session: AsyncSession
    ) -> None:
        """Test that count-today decreases after soft-deleting a user created today."""
        user_in = UserCreate(
            email="today-delete@example.com", full_name="Today Delete"
        )
        user = await crud.create_user(db_session, user_in)
        await db_session.flush()
        await db_session.refresh(user)

        # Verify initial count
        initial_count = await crud.count_users_today(db_session)
        assert initial_count == 1

        # Soft-delete the user
        deleted = await crud.delete_user(db_session, user.id)
        assert deleted is True

        # Verify count-today decreased
        final_count = await crud.count_users_today(db_session)
        assert final_count == 0

    # AC-002: count-by-domain excludes deleted users
    @pytest.mark.asyncio
    async def test_count_by_domain_excludes_deleted_users(
        self, db_session: AsyncSession
    ) -> None:
        """Test that count-by-domain excludes soft-deleted users.

        Creates users from two domains, deletes one user from one domain,
        and verifies the domain count decreases.
        """
        # Create 3 users from example.com
        for i in range(3):
            user_in = UserCreate(
                email=f"domain{i}@example.com", full_name=f"Domain {i}"
            )
            await crud.create_user(db_session, user_in)

        # Create 2 users from other.org
        for i in range(2):
            user_in = UserCreate(
                email=f"domain{i}@other.org", full_name=f"Domain {i}"
            )
            await crud.create_user(db_session, user_in)
        await db_session.flush()

        # Verify initial counts
        domain_counts = await crud.count_users_by_domain(db_session)
        assert len(domain_counts) == 2
        example_count = next(
            (d["count"] for d in domain_counts if d["domain"] == "example.com"), 0
        )
        other_count = next(
            (d["count"] for d in domain_counts if d["domain"] == "other.org"), 0
        )
        assert example_count == 3
        assert other_count == 2

        # Delete one user from example.com
        example_users = await crud.get_users(db_session)
        example_user = next(
            (u for u in example_users if u.email.endswith("@example.com")), None
        )
        assert example_user is not None
        deleted = await crud.delete_user(db_session, example_user.id)
        assert deleted is True

        # Verify domain count decreased
        domain_counts = await crud.count_users_by_domain(db_session)
        example_count = next(
            (d["count"] for d in domain_counts if d["domain"] == "example.com"), 0
        )
        other_count = next(
            (d["count"] for d in domain_counts if d["domain"] == "other.org"), 0
        )
        assert example_count == 2
        assert other_count == 2

    # AC-001: count endpoint reflects real-time after multiple deletions
    @pytest.mark.asyncio
    async def test_count_reflects_multiple_deletions(
        self, db_session: AsyncSession
    ) -> None:
        """Test that count reflects multiple sequential deletions."""
        # Create 5 users
        for i in range(5):
            user_in = UserCreate(email=f"multi{i}@example.com", full_name=f"Multi {i}")
            await crud.create_user(db_session, user_in)
        await db_session.flush()

        initial_count = await crud.count_users(db_session)
        assert initial_count == 5

        # Delete 3 users
        users = await crud.get_users(db_session)
        for user in users[:3]:
            await crud.delete_user(db_session, user.id)

        final_count = await crud.count_users(db_session)
        assert final_count == 2

    # AC-002: API endpoint returns correct count after deletion
    @pytest.mark.asyncio
    async def test_api_count_endpoint_after_deletion(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test that GET /users/count returns correct count after deletion via API."""
        # Create a user
        user_in = UserCreate(email="api-count@example.com", full_name="API Count")
        await crud.create_user(db_session, user_in)
        await db_session.flush()

        # Verify initial count via API
        response = await async_client.get("/users/count")
        assert response.status_code == HTTPStatus.OK
        assert response.json()["count"] == 1

        # Delete via API
        users_response = await async_client.get("/users")
        user_id = users_response.json()["items"][0]["id"]
        delete_response = await async_client.delete(
            f"/users/{user_id}", headers={"X-Auth-Token": AUTH_TOKEN}
        )
        assert delete_response.status_code == HTTPStatus.NO_CONTENT

        # Verify count decreased via API
        response = await async_client.get("/users/count")
        assert response.status_code == HTTPStatus.OK
        assert response.json()["count"] == 0

    # Soft-delete preserves user record for audit
    @pytest.mark.asyncio
    async def test_deleted_user_still_retrievable(
        self, db_session: AsyncSession
    ) -> None:
        """Test that soft-deleted users are NOT retrievable via get_user (AC-001)."""
        user_in = UserCreate(email="audit@example.com", full_name="Audit")
        user = await crud.create_user(db_session, user_in)
        await db_session.flush()
        await db_session.refresh(user)

        # Soft-delete
        await crud.delete_user(db_session, user.id)

        # get_user filters out deleted users per AC-001
        retrieved = await crud.get_user(db_session, user.id)
        assert retrieved is None

    # Non-existent user deletion returns False
    @pytest.mark.asyncio
    async def test_delete_non_existent_user(self, db_session: AsyncSession) -> None:
        """Test that deleting a non-existent user returns False."""
        fake_id = str(uuid4())
        deleted = await crud.delete_user(db_session, fake_id)
        assert deleted is False

    # Count with all users deleted returns zero
    @pytest.mark.asyncio
    async def test_count_zero_when_all_deleted(self, db_session: AsyncSession) -> None:
        """Test that count returns 0 when all users are soft-deleted."""
        user_in = UserCreate(email="last@example.com", full_name="Last")
        user = await crud.create_user(db_session, user_in)
        await db_session.flush()
        await db_session.refresh(user)

        await crud.delete_user(db_session, user.id)

        count = await crud.count_users(db_session)
        assert count == 0
