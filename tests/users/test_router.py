"""Tests for users API router."""

from __future__ import annotations

from http import HTTPStatus
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.models import User
from src.users.schemas import UserCreate


class TestCreateUser:
    """Tests for POST /users endpoint."""

    @pytest.mark.asyncio
    async def test_create_user_success(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test successful user creation."""
        payload = {
            "email": "newuser@example.com",
            "full_name": "New User",
        }

        response = await async_client.post("/users", json=payload)

        assert response.status_code == HTTPStatus.CREATED
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["full_name"] == "New User"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_create_user_minimal(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test user creation with only required field."""
        payload = {"email": "minimal@example.com"}

        response = await async_client.post("/users", json=payload)

        assert response.status_code == HTTPStatus.CREATED
        data = response.json()
        assert data["email"] == "minimal@example.com"
        assert data["full_name"] is None

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that creating a user with existing email returns 409."""
        # Create first user using db_session fixture
        user_in = UserCreate(email="duplicate@example.com", full_name="First")
        await crud.create_user(db_session, user_in)

        # Try to create second user with same email
        payload = {"email": "duplicate@example.com", "full_name": "Second"}

        response = await async_client.post("/users", json=payload)

        assert response.status_code == HTTPStatus.CONFLICT
        data = response.json()
        assert "already exists" in data["detail"]


class TestListUsers:
    """Tests for GET /users endpoint."""

    @pytest.mark.asyncio
    async def test_list_users_empty(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test listing users when database is empty."""
        response = await async_client.get("/users")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_users_with_data(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test listing users with existing data."""
        # Create users
        for i in range(3):
            await crud.create_user(
                db_session,
                UserCreate(
                    email=f"user{i}@example.com", full_name=f"User {i}"
                ),
            )

        response = await async_client.get("/users")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

    @pytest.mark.asyncio
    async def test_list_users_pagination(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test listing users with pagination."""
        # Create 10 users
        for i in range(10):
            await crud.create_user(
                db_session,
                UserCreate(email=f"pag{i}@example.com", full_name=f"Pag {i}"),
            )

        # Test skip
        response = await async_client.get("/users?skip=5")
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data["items"]) == 5
        assert data["total"] == 10

        # Test limit
        response = await async_client.get("/users?limit=3")
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 10

        # Test both
        response = await async_client.get("/users?skip=2&limit=3")
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 10


class TestGetUser:
    """Tests for GET /users/{user_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_user_found(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test getting an existing user."""
        user_in = UserCreate(email="get@example.com", full_name="Get User")
        created = await crud.create_user(db_session, user_in)

        response = await async_client.get(f"/users/{created.id}")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["email"] == "get@example.com"
        assert data["full_name"] == "Get User"
        assert data["id"] == created.id

    @pytest.mark.asyncio
    async def test_get_user_not_found(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test getting a non-existent user returns 404."""
        fake_id = str(uuid4())

        response = await async_client.get(f"/users/{fake_id}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"]


class TestUpdateUser:
    """Tests for PUT /users/{user_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_user_found(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test updating an existing user."""
        user_in = UserCreate(email="update@example.com", full_name="Original")
        created = await crud.create_user(db_session, user_in)

        payload = {"full_name": "Updated Name", "is_active": False}

        response = await async_client.put(f"/users/{created.id}", json=payload)

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["full_name"] == "Updated Name"
        assert data["is_active"] is False
        assert data["email"] == "update@example.com"  # Unchanged

    @pytest.mark.asyncio
    async def test_update_user_partial(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that update only modifies provided fields."""
        user_in = UserCreate(email="partial@example.com", full_name="Original")
        created = await crud.create_user(db_session, user_in)

        # Update only is_active
        payload = {"is_active": False}

        response = await async_client.put(f"/users/{created.id}", json=payload)

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["is_active"] is False
        assert data["full_name"] == "Original"  # Unchanged

    @pytest.mark.asyncio
    async def test_update_user_not_found(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test updating a non-existent user returns 404."""
        fake_id = str(uuid4())

        response = await async_client.put(f"/users/{fake_id}", json={"full_name": "New"})

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"]


class TestDeleteUser:
    """Tests for DELETE /users/{user_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_user_found(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test deleting an existing user returns 204."""
        user_in = UserCreate(email="delete@example.com", full_name="Delete User")
        created = await crud.create_user(db_session, user_in)

        response = await async_client.delete(f"/users/{created.id}")

        assert response.status_code == HTTPStatus.NO_CONTENT

        # Verify user is actually deleted
        response = await async_client.get(f"/users/{created.id}")
        assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_user_not_found(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test deleting a non-existent user returns 404."""
        fake_id = str(uuid4())

        response = await async_client.delete(f"/users/{fake_id}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"]


class TestGetUserCount:
    """Tests for GET /users/count endpoint."""

    @pytest.mark.asyncio
    async def test_count_empty(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test count returns 0 when database is empty."""
        response = await async_client.get("/users/count")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data == {"count": 0}

    @pytest.mark.asyncio
    async def test_count_incremental(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that count increments after creating users."""
        # Initial count should be 0
        response = await async_client.get("/users/count")
        assert response.status_code == HTTPStatus.OK
        assert response.json()["count"] == 0

        # Create a user
        await crud.create_user(
            db_session,
            UserCreate(email="increment@example.com", full_name="Increment"),
        )

        # Count should be 1
        response = await async_client.get("/users/count")
        assert response.status_code == HTTPStatus.OK
        assert response.json()["count"] == 1

        # Create another user
        await crud.create_user(
            db_session,
            UserCreate(email="increment2@example.com", full_name="Increment 2"),
        )

        # Count should be 2
        response = await async_client.get("/users/count")
        assert response.status_code == HTTPStatus.OK
        assert response.json()["count"] == 2

    @pytest.mark.asyncio
    async def test_count_method_not_allowed(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that POST to /users/count returns 405."""
        response = await async_client.post("/users/count", json={"email": "x@x.com"})
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    @pytest.mark.asyncio
    async def test_count_method_not_allowed_put_delete(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that PUT/DELETE to /users/count are rejected (405 or 422)."""
        # PUT - FastAPI may return 422 for unmatched methods with body
        response = await async_client.put("/users/count", json={"full_name": "X"})
        assert response.status_code in (
            HTTPStatus.METHOD_NOT_ALLOWED,
            HTTPStatus.UNPROCESSABLE_ENTITY,
        )

        # DELETE - FastAPI may return 422 for unmatched methods
        response = await async_client.delete("/users/count")
        assert response.status_code in (
            HTTPStatus.METHOD_NOT_ALLOWED,
            HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    @pytest.mark.asyncio
    async def test_count_returns_non_negative(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that count is always a non-negative integer."""
        response = await async_client.get("/users/count")
        data = response.json()
        assert isinstance(data["count"], int)
        assert data["count"] >= 0

    @pytest.mark.asyncio
    async def test_get_user_by_id_still_works(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Regression guard: GET /users/{user_id} still works after adding count route."""
        user_in = UserCreate(email="regression@example.com", full_name="Regression")
        created = await crud.create_user(db_session, user_in)

        response = await async_client.get(f"/users/{created.id}")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["email"] == "regression@example.com"
        assert data["full_name"] == "Regression"

    @pytest.mark.asyncio
    async def test_count_db_unavailable(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that count returns 503 when database is unavailable."""
        from unittest.mock import AsyncMock

        from sqlalchemy.exc import SQLAlchemyError

        # Mock crud.count_users to raise a DB error
        original_count_users = crud.count_users
        crud.count_users = AsyncMock(side_effect=SQLAlchemyError("Connection refused"))

        try:
            response = await async_client.get("/users/count")
            assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
            data = response.json()
            assert "Database unavailable" in data["detail"]
            assert "Connection refused" in data["detail"]
        finally:
            crud.count_users = original_count_users


class TestGetUserByEmail:
    """Tests for GET /users/by-email endpoint."""

    @pytest.mark.asyncio
    async def test_by_email_found(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that looking up an existing email returns 200 with user data."""
        user_in = UserCreate(email="byemail@example.com", full_name="By Email")
        created = await crud.create_user(db_session, user_in)

        response = await async_client.get("/users/by-email", params={"email": "byemail@example.com"})

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["email"] == "byemail@example.com"
        assert data["full_name"] == "By Email"
        assert data["id"] == created.id
        assert data["is_active"] is True
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_by_email_multiple_users_exact_match(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that lookup returns exactly the matching user among several."""
        for i in range(3):
            await crud.create_user(
                db_session,
                UserCreate(email=f"multi{i}@example.com", full_name=f"Multi {i}"),
            )

        response = await async_client.get("/users/by-email", params={"email": "multi1@example.com"})

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["email"] == "multi1@example.com"
        assert data["full_name"] == "Multi 1"

    @pytest.mark.asyncio
    async def test_by_email_not_found(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that an unknown email returns 404 with clear detail."""
        response = await async_client.get("/users/by-email", params={"email": "unknown@example.com"})

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()
        assert "unknown@example.com" in data["detail"]

    @pytest.mark.asyncio
    async def test_by_email_malformed_returns_422(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that a malformed email returns 422 without hitting the database."""
        response = await async_client.get("/users/by-email", params={"email": "not-an-email"})

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_by_email_db_unavailable(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that by-email returns 503 when database is unavailable."""
        from unittest.mock import AsyncMock

        from sqlalchemy.exc import SQLAlchemyError

        original_get_by_email = crud.get_user_by_email
        crud.get_user_by_email = AsyncMock(side_effect=SQLAlchemyError("Connection refused"))

        try:
            response = await async_client.get("/users/by-email", params={"email": "x@example.com"})
            assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
            data = response.json()
            assert "Database unavailable" in data["detail"]
            assert "Connection refused" in data["detail"]
        finally:
            crud.get_user_by_email = original_get_by_email

    @pytest.mark.asyncio
    async def test_by_email_case_sensitive(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that email lookup is exact match (case-sensitive)."""
        await crud.create_user(
            db_session,
            UserCreate(email="CaseSensitive@example.com", full_name="Case Test"),
        )

        response_upper = await async_client.get("/users/by-email", params={"email": "CASESENSITIVE@EXAMPLE.COM"})
        assert response_upper.status_code == HTTPStatus.NOT_FOUND

        response_exact = await async_client.get("/users/by-email", params={"email": "CaseSensitive@example.com"})
        assert response_exact.status_code == HTTPStatus.OK
        assert response_exact.json()["full_name"] == "Case Test"

    @pytest.mark.asyncio
    async def test_by_id_still_works_after_by_email(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Regression guard: GET /users/{user_id} still works after adding by-email route."""
        user_in = UserCreate(email="regression2@example.com", full_name="Regression 2")
        created = await crud.create_user(db_session, user_in)

        response = await async_client.get(f"/users/{created.id}")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["email"] == "regression2@example.com"
        assert data["full_name"] == "Regression 2"
