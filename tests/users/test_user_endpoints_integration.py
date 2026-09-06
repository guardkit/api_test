"""Integration tests for user endpoints.

These tests exercise the full API stack for user-related endpoints:
- GET /users/count-by-domain (fresh and existing databases)
- POST /users (fresh database)

Tests use the async_client fixture with dependency overrides to hit
the actual FastAPI router and assert lasting invariants about the API
behaviour rather than point-in-time snapshots.
"""

from __future__ import annotations

from http import HTTPStatus

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate

# ====================================================================
# AC-001: Tests for GET /users/count-by-domain on fresh database
# ====================================================================


class TestCountByDomainFreshDatabase:
    """Integration tests for GET /users/count-by-domain on a fresh (empty) database."""

    async def test_count_by_domain_returns_empty_list(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """GET /users/count-by-domain returns an empty JSON array on fresh database.

        On a database with no users, the endpoint must return a 200 OK with an
        empty JSON array -- not an error, not a wrapper object.
        """
        response = await async_client.get("/users/count-by-domain")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_count_by_domain_response_is_json_array(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """GET /users/count-by-domain returns a valid JSON array (not object).

        The response body must be serialisable as a JSON array at the top level.
        """
        response = await async_client.get("/users/count-by-domain")

        assert response.status_code == HTTPStatus.OK
        # Verify the raw body parses as a JSON array
        data = response.json()
        assert data == []

    async def test_count_by_domain_content_type_is_json(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """GET /users/count-by-domain sets Content-Type to application/json."""
        response = await async_client.get("/users/count-by-domain")

        assert response.status_code == HTTPStatus.OK
        assert "application/json" in response.headers.get("content-type", "")


# ====================================================================
# AC-002: Tests for GET /users/count-by-domain on existing database
# ====================================================================


class TestCountByDomainExistingDatabase:
    """Integration tests for GET /users/count-by-domain on a database with data."""

    async def test_count_by_domain_single_domain(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """GET /users/count-by-domain returns correct counts for a single domain.

        When all users belong to the same domain, the response must contain
        exactly one entry with the correct count.
        """
        for i in range(3):
            user_in = UserCreate(
                email=f"user{i}@example.com",
                full_name=f"User {i}",
            )
            await crud.create_user(db_session, user_in)

        response = await async_client.get("/users/count-by-domain")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["domain"] == "example.com"
        assert data[0]["count"] == 3

    async def test_count_by_domain_multiple_domains_ordered(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """GET /users/count-by-domain orders results by count descending.

        When users belong to multiple domains, the response must be sorted
        by count in descending order -- the domain with the most users
        appears first.
        """
        # 5 users from other.org
        for i in range(5):
            await crud.create_user(
                db_session,
                UserCreate(email=f"user{i}@other.org", full_name=f"User {i}"),
            )
        # 3 users from example.com
        for i in range(3):
            await crud.create_user(
                db_session,
                UserCreate(email=f"user{i}@example.com", full_name=f"User {i}"),
            )
        # 1 user from third.net
        await crud.create_user(
            db_session,
            UserCreate(email="single@third.net", full_name="Single User"),
        )

        response = await async_client.get("/users/count-by-domain")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == 3
        # Verify descending order by count
        assert data[0]["domain"] == "other.org"
        assert data[0]["count"] == 5
        assert data[1]["domain"] == "example.com"
        assert data[1]["count"] == 3
        assert data[2]["domain"] == "third.net"
        assert data[2]["count"] == 1

    async def test_count_by_domain_domain_extraction(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """GET /users/count-by-domain correctly extracts domains from emails.

        The domain is derived from everything after the '@' in the email
        address. Subdomains are preserved as part of the domain.
        """
        await crud.create_user(
            db_session,
            UserCreate(email="user@sub.domain.com", full_name="Sub User"),
        )
        await crud.create_user(
            db_session,
            UserCreate(email="admin@sub.domain.com", full_name="Sub Admin"),
        )
        await crud.create_user(
            db_session,
            UserCreate(email="test@another-domain.org", full_name="Test User"),
        )

        response = await async_client.get("/users/count-by-domain")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == 2
        assert data[0]["domain"] == "sub.domain.com"
        assert data[0]["count"] == 2
        assert data[1]["domain"] == "another-domain.org"
        assert data[1]["count"] == 1

    async def test_count_by_domain_min_count_filter(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """GET /users/count-by-domain respects the min_count query parameter.

        When min_count is provided, only domains with count >= min_count
        should appear in the response.
        """
        # 5 users from big.com
        for i in range(5):
            await crud.create_user(
                db_session,
                UserCreate(email=f"user{i}@big.com", full_name=f"User {i}"),
            )
        # 2 users from small.com
        for i in range(2):
            await crud.create_user(
                db_session,
                UserCreate(email=f"user{i}@small.com", full_name=f"User {i}"),
            )

        response = await async_client.get(
            "/users/count-by-domain", params={"min_count": 3}
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["domain"] == "big.com"
        assert data[0]["count"] == 5

    async def test_count_by_domain_min_count_no_match(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """GET /users/count-by-domain returns empty list when min_count
        exceeds all counts."""
        for i in range(2):
            await crud.create_user(
                db_session,
                UserCreate(email=f"user{i}@example.com", full_name=f"User {i}"),
            )

        response = await async_client.get(
            "/users/count-by-domain", params={"min_count": 10}
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == 0

    async def test_count_by_domain_each_entry_has_domain_and_count(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Each entry in the response must have 'domain' (str) and 'count' (int)."""
        await crud.create_user(
            db_session,
            UserCreate(email="user@example.com", full_name="User"),
        )

        response = await async_client.get("/users/count-by-domain")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) >= 1
        for entry in data:
            assert "domain" in entry
            assert "count" in entry
            assert isinstance(entry["domain"], str)
            assert isinstance(entry["count"], int)


# ====================================================================
# AC-003: Tests for POST /users on fresh database
# ====================================================================


class TestCreateUserFreshDatabase:
    """Integration tests for POST /users on a fresh (empty) database."""

    async def test_create_user_returns_201(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """POST /users on fresh database returns 201 Created.

        Creating a user on an empty database must succeed and return
        HTTP 201 with the created user object.
        """
        payload = {
            "email": "fresh.user@example.com",
            "full_name": "Fresh User",
        }

        response = await async_client.post("/users", json=payload)

        assert response.status_code == HTTPStatus.CREATED
        data = response.json()
        assert data["email"] == "fresh.user@example.com"
        assert data["full_name"] == "Fresh User"

    async def test_create_user_response_contains_id(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """POST /users response includes a non-empty UUID string as 'id'."""
        payload = {"email": "id.test@example.com", "full_name": "ID Test"}

        response = await async_client.post("/users", json=payload)

        assert response.status_code == HTTPStatus.CREATED
        data = response.json()
        assert "id" in data
        assert isinstance(data["id"], str)
        assert len(data["id"]) > 0

    async def test_create_user_response_contains_timestamps(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """POST /users response includes created_at and updated_at fields."""
        payload = {"email": "timestamp.test@example.com", "full_name": "Timestamp"}

        response = await async_client.post("/users", json=payload)

        assert response.status_code == HTTPStatus.CREATED
        data = response.json()
        assert "created_at" in data
        assert "updated_at" in data
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)

    async def test_create_user_auto_domain_extraction(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """POST /users auto-extracts domain from email when not provided."""
        payload = {
            "email": "auto.domain@example.com",
            "full_name": "Auto Domain",
        }

        response = await async_client.post("/users", json=payload)

        assert response.status_code == HTTPStatus.CREATED
        data = response.json()
        assert data["domain"] == "example.com"

    async def test_create_user_is_active_default_true(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """POST /users sets is_active to True by default."""
        payload = {"email": "active.test@example.com", "full_name": "Active Test"}

        response = await async_client.post("/users", json=payload)

        assert response.status_code == HTTPStatus.CREATED
        data = response.json()
        assert data["is_active"] is True

    async def test_create_user_minimal_payload(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """POST /users accepts minimal payload with only email."""
        payload = {"email": "minimal.fresh@example.com"}

        response = await async_client.post("/users", json=payload)

        assert response.status_code == HTTPStatus.CREATED
        data = response.json()
        assert data["email"] == "minimal.fresh@example.com"
        assert data["full_name"] is None
        assert data["name"] is None

    async def test_create_user_persists_to_database(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """POST /users on fresh database persists the user so it can be retrieved.

        After creation, the user must exist in the database and be queryable
        via the CRUD layer -- confirming the write actually persisted.
        """
        payload = {
            "email": "persist.test@example.com",
            "full_name": "Persist Test",
        }

        response = await async_client.post("/users", json=payload)

        assert response.status_code == HTTPStatus.CREATED
        created_id = response.json()["id"]

        # Verify the user was persisted by querying the DB directly
        user = await crud.get_user(db_session, created_id)
        assert user is not None
        assert user.email == "persist.test@example.com"
        assert user.full_name == "Persist Test"
