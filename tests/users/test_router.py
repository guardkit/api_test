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
