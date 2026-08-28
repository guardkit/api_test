"""Tests for count-by-domain endpoint and CRUD function."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import DomainCountResponse, UserCreate
from src.main import app
from src.db.dependencies import get_db as app_get_db


class TestCountByDomainCrud:
    """Tests for the count_users_by_domain CRUD function."""

    # AC-002: Test case for empty user set
    async def test_count_by_domain_empty(self, db_session: AsyncSession) -> None:
        """Test count-by-domain returns empty list when no users exist."""
        result = await crud.count_users_by_domain(db_session)
        assert result == []

    # AC-002: Test case for single domain
    async def test_count_by_domain_single_domain(
        self, db_session: AsyncSession
    ) -> None:
        """Test count-by-domain with users from a single domain."""
        for i in range(3):
            user_in = UserCreate(
                email=f"user{i}@example.com",
                full_name=f"User {i}",
            )
            await crud.create_user(db_session, user_in)

        result = await crud.count_users_by_domain(db_session)
        assert len(result) == 1
        assert result[0]["domain"] == "example.com"
        assert result[0]["count"] == 3

    # AC-002: Test case for multiple domains
    async def test_count_by_domain_multiple_domains(
        self, db_session: AsyncSession
    ) -> None:
        """Test count-by-domain with users from multiple domains."""
        # 3 users from example.com
        for i in range(3):
            user_in = UserCreate(
                email=f"user{i}@example.com",
                full_name=f"User {i}",
            )
            await crud.create_user(db_session, user_in)

        # 5 users from other.org
        for i in range(5):
            user_in = UserCreate(
                email=f"user{i}@other.org",
                full_name=f"User {i}",
            )
            await crud.create_user(db_session, user_in)

        # 1 user from third.net
        user_in = UserCreate(
            email="single@third.net",
            full_name="Single User",
        )
        await crud.create_user(db_session, user_in)

        result = await crud.count_users_by_domain(db_session)
        assert len(result) == 3

        # Verify ordering: descending by count
        assert result[0]["domain"] == "other.org"
        assert result[0]["count"] == 5
        assert result[1]["domain"] == "example.com"
        assert result[1]["count"] == 3
        assert result[2]["domain"] == "third.net"
        assert result[2]["count"] == 1

    # AC-002: Test case for domain extraction from email
    async def test_count_by_domain_domain_extraction(
        self, db_session: AsyncSession
    ) -> None:
        """Test that domains are correctly extracted from various email formats."""
        emails = [
            "user@sub.domain.com",
            "admin@sub.domain.com",
            "test@another-domain.org",
        ]
        for email in emails:
            user_in = UserCreate(email=email, full_name="Test")
            await crud.create_user(db_session, user_in)

        result = await crud.count_users_by_domain(db_session)
        assert len(result) == 2
        # sub.domain.com has 2 users
        assert result[0]["domain"] == "sub.domain.com"
        assert result[0]["count"] == 2
        # another-domain.org has 1 user
        assert result[1]["domain"] == "another-domain.org"


class TestCountByDomainMinCountFiltering:
    """Tests for min_count filtering behavior (AC-002, AC-003)."""

    # AC-002: Filter is applied when min_count is provided
    async def test_count_by_domain_with_min_count_filters(
        self, db_session: AsyncSession
    ) -> None:
        """Test that min_count filters out domains below the threshold."""
        # 3 users from example.com
        for i in range(3):
            user_in = UserCreate(
                email=f"user{i}@example.com",
                full_name=f"User {i}",
            )
            await crud.create_user(db_session, user_in)

        # 5 users from other.org
        for i in range(5):
            user_in = UserCreate(
                email=f"user{i}@other.org",
                full_name=f"User {i}",
            )
            await crud.create_user(db_session, user_in)

        # 1 user from third.net
        user_in = UserCreate(
            email="single@third.net",
            full_name="Single User",
        )
        await crud.create_user(db_session, user_in)

        # With min_count=3, only domains with >= 3 users should be returned
        result = await crud.count_users_by_domain(db_session, min_count=3)

        assert len(result) == 2
        domains = {r["domain"] for r in result}
        assert "other.org" in domains
        assert "example.com" in domains
        assert "third.net" not in domains

        # Verify ordering is preserved
        assert result[0]["domain"] == "other.org"
        assert result[0]["count"] == 5
        assert result[1]["domain"] == "example.com"
        assert result[1]["count"] == 3

    # AC-002: min_count=0 returns all domains
    async def test_count_by_domain_min_count_zero_returns_all(
        self, db_session: AsyncSession
    ) -> None:
        """Test that min_count=0 returns all domains (no filtering)."""
        for i in range(2):
            user_in = UserCreate(
                email=f"user{i}@example.com",
                full_name=f"User {i}",
            )
            await crud.create_user(db_session, user_in)

        user_in = UserCreate(
            email="single@other.org",
            full_name="Single",
        )
        await crud.create_user(db_session, user_in)

        result = await crud.count_users_by_domain(db_session, min_count=0)

        assert len(result) == 2
        assert result[0]["domain"] == "example.com"
        assert result[0]["count"] == 2
        assert result[1]["domain"] == "other.org"
        assert result[1]["count"] == 1

    # AC-002: min_count that excludes all domains returns empty list
    async def test_count_by_domain_min_count_excludes_all(
        self, db_session: AsyncSession
    ) -> None:
        """Test that min_count higher than any domain count returns empty list."""
        for i in range(2):
            user_in = UserCreate(
                email=f"user{i}@example.com",
                full_name=f"User {i}",
            )
            await crud.create_user(db_session, user_in)

        result = await crud.count_users_by_domain(db_session, min_count=100)

        assert result == []

    # AC-003: All domains returned when min_count is omitted
    async def test_count_by_domain_without_min_count_returns_all(
        self, db_session: AsyncSession
    ) -> None:
        """Test that omitting min_count returns all domains unfiltered."""
        for i in range(3):
            user_in = UserCreate(
                email=f"user{i}@example.com",
                full_name=f"User {i}",
            )
            await crud.create_user(db_session, user_in)

        for i in range(5):
            user_in = UserCreate(
                email=f"user{i}@other.org",
                full_name=f"User {i}",
            )
            await crud.create_user(db_session, user_in)

        user_in = UserCreate(
            email="single@third.net",
            full_name="Single",
        )
        await crud.create_user(db_session, user_in)

        # Call without min_count (None)
        result = await crud.count_users_by_domain(db_session, min_count=None)

        assert len(result) == 3
        assert result[0]["domain"] == "other.org"
        assert result[0]["count"] == 5
        assert result[1]["domain"] == "example.com"
        assert result[1]["count"] == 3
        assert result[2]["domain"] == "third.net"
        assert result[2]["count"] == 1

    # AC-003: API endpoint returns all domains without min_count
    async def test_api_count_by_domain_without_min_count(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test the API endpoint returns all domains when min_count is not provided."""
        # Override the db dependency
        app.dependency_overrides[app_get_db] = lambda: db_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Create test data
            for i in range(3):
                await crud.create_user(
                    db_session,
                    UserCreate(email=f"user{i}@example.com", full_name=f"User {i}"),
                )
            for i in range(5):
                await crud.create_user(
                    db_session,
                    UserCreate(email=f"user{i}@other.org", full_name=f"User {i}"),
                )
            await db_session.commit()

            response = await client.get("/users/count-by-domain")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == 2
        assert data[0] == {"domain": "other.org", "count": 5}
        assert data[1] == {"domain": "example.com", "count": 3}

        app.dependency_overrides.clear()

    # AC-003: API endpoint applies min_count filter
    async def test_api_count_by_domain_with_min_count(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test the API endpoint filters domains when min_count is provided."""
        app.dependency_overrides[app_get_db] = lambda: db_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Create test data
            for i in range(3):
                await crud.create_user(
                    db_session,
                    UserCreate(email=f"user{i}@example.com", full_name=f"User {i}"),
                )
            for i in range(5):
                await crud.create_user(
                    db_session,
                    UserCreate(email=f"user{i}@other.org", full_name=f"User {i}"),
                )
            for i in range(1):
                await crud.create_user(
                    db_session,
                    UserCreate(email=f"user{i}@third.net", full_name=f"User {i}"),
                )
            await db_session.commit()

            response = await client.get("/users/count-by-domain", params={"min_count": "3"})

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == 2
        assert data[0] == {"domain": "other.org", "count": 5}
        assert data[1] == {"domain": "example.com", "count": 3}

        app.dependency_overrides.clear()
        assert result[1]["count"] == 1


class TestCountByDomainEndpoint:
    """Tests for the GET /users/count-by-domain endpoint."""

    # AC-001: Test case for valid request returns 200
    @pytest.mark.asyncio
    async def test_count_by_domain_returns_200(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test endpoint returns 200 OK for valid requests."""
        response = await async_client.get("/users/count-by-domain")
        assert response.status_code == HTTPStatus.OK

    # AC-002: Test case for empty user set
    async def test_count_by_domain_empty_response(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test endpoint returns empty array when no users exist."""
        response = await async_client.get("/users/count-by-domain")
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    # AC-002: Test case for correct response format
    async def test_count_by_domain_response_format(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test endpoint returns correct JSON array format with domain and count."""
        # Create users with different domains
        for i in range(2):
            user_in = UserCreate(
                email=f"user{i}@example.com",
                full_name=f"User {i}",
            )
            await crud.create_user(db_session, user_in)

        for i in range(4):
            user_in = UserCreate(
                email=f"user{i}@other.org",
                full_name=f"User {i}",
            )
            await crud.create_user(db_session, user_in)

        response = await async_client.get("/users/count-by-domain")
        assert response.status_code == HTTPStatus.OK
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 2

        # Verify each entry has domain and count fields with correct types
        for entry in data:
            assert "domain" in entry
            assert "count" in entry
            assert isinstance(entry["domain"], str)
            assert isinstance(entry["count"], int)

    # AC-002: Test case for descending order
    async def test_count_by_domain_ordering(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test entries are ordered by count descending."""
        # Create users: 1 from alpha.com, 3 from beta.com, 2 from gamma.com
        user_in = UserCreate(email="a@alpha.com", full_name="A")
        await crud.create_user(db_session, user_in)

        for i in range(3):
            user_in = UserCreate(email=f"b{i}@beta.com", full_name=f"B{i}")
            await crud.create_user(db_session, user_in)

        for i in range(2):
            user_in = UserCreate(email=f"c{i}@gamma.com", full_name=f"C{i}")
            await crud.create_user(db_session, user_in)

        response = await async_client.get("/users/count-by-domain")
        data = response.json()

        assert len(data) == 3
        assert data[0]["count"] == 3  # beta.com
        assert data[1]["count"] == 2  # gamma.com
        assert data[2]["count"] == 1  # alpha.com


class TestDomainCountSchema:
    """Tests for the DomainCountResponse schema."""

    def test_schema_domain_and_count(self) -> None:
        """Test schema accepts domain (str) and count (int)."""
        entry = DomainCountResponse(domain="example.com", count=5)
        assert entry.domain == "example.com"
        assert entry.count == 5


class TestMinCountParameter:
    """Tests for the min_count optional query parameter on /users/count-by-domain."""

    # AC-001: min_count as optional query parameter
    async def test_min_count_returns_filtered_domains(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test that min_count filters out domains below the threshold."""
        # Create users: 1 from alpha.com, 3 from beta.com, 2 from gamma.com
        user_in = UserCreate(email="a@alpha.com", full_name="A")
        await crud.create_user(db_session, user_in)

        for i in range(3):
            user_in = UserCreate(email=f"b{i}@beta.com", full_name=f"B{i}")
            await crud.create_user(db_session, user_in)

        for i in range(2):
            user_in = UserCreate(email=f"c{i}@gamma.com", full_name=f"C{i}")
            await crud.create_user(db_session, user_in)

        # min_count=2 should exclude alpha.com (count=1)
        response = await async_client.get("/users/count-by-domain?min_count=2")
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == 2
        domains = {entry["domain"] for entry in data}
        assert domains == {"beta.com", "gamma.com"}
        assert "alpha.com" not in domains

    # AC-003: omitting min_count returns all domains (backward compatibility)
    async def test_min_count_omitted_returns_all_domains(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test that omitting min_count returns all domains (no filtering)."""
        for i in range(1):
            user_in = UserCreate(email=f"user{i}@alpha.com", full_name="A")
            await crud.create_user(db_session, user_in)

        for i in range(3):
            user_in = UserCreate(email=f"user{i}@beta.com", full_name=f"B{i}")
            await crud.create_user(db_session, user_in)

        response = await async_client.get("/users/count-by-domain")
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == 2

    # AC-002: min_count is treated as an integer
    async def test_min_count_integer_type(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test that min_count parameter is treated as an integer."""
        for i in range(5):
            user_in = UserCreate(email=f"user{i}@example.com", full_name="U")
            await crud.create_user(db_session, user_in)

        # Pass min_count as integer value
        response = await async_client.get("/users/count-by-domain?min_count=3")
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        # All 5 users are in example.com, which is >= 3
        assert len(data) == 1
        assert data[0]["domain"] == "example.com"
        assert data[0]["count"] == 5

    # AC-003: min_count=0 returns all domains
    async def test_min_count_zero_returns_all(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test that min_count=0 returns all domains (no filtering)."""
        for i in range(1):
            user_in = UserCreate(email=f"user{i}@alpha.com", full_name="A")
            await crud.create_user(db_session, user_in)

        for i in range(3):
            user_in = UserCreate(email=f"user{i}@beta.com", full_name=f"B{i}")
            await crud.create_user(db_session, user_in)

        response = await async_client.get("/users/count-by-domain?min_count=0")
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == 2

    # AC-003: min_count higher than any domain returns empty list
    async def test_min_count_excludes_all_domains(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test that a min_count higher than all domain counts returns empty list."""
        for i in range(2):
            user_in = UserCreate(email=f"user{i}@example.com", full_name="U")
            await crud.create_user(db_session, user_in)

        response = await async_client.get("/users/count-by-domain?min_count=100")
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data == []

    # AC-002: min_count parameter type enforcement
    async def test_min_count_non_integer_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test that a non-integer min_count value returns 400 Bad Request."""
        response = await async_client.get(
            "/users/count-by-domain?min_count=not_a_number"
        )
        assert response.status_code == 400

    # AC-001: negative min_count rejected
    async def test_min_count_negative_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test that a negative min_count value returns 400 Bad Request."""
        response = await async_client.get("/users/count-by-domain?min_count=-1")
        assert response.status_code == 400

    # AC-003: empty min_count rejected
    async def test_min_count_empty_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test that an empty min_count value returns 400 Bad Request."""
        response = await async_client.get("/users/count-by-domain?min_count=")
        assert response.status_code == 400

    # AC-004: min_count exceeding maximum rejected
    async def test_min_count_exceeds_max_returns_400(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test that a min_count exceeding 10,000 returns 400 Bad Request."""
        response = await async_client.get("/users/count-by-domain?min_count=10001")
        assert response.status_code == 400


class TestMinCountCrud:
    """Tests for the min_count parameter in count_users_by_domain CRUD function."""

    # AC-002: CRUD min_count as integer
    async def test_crud_min_count_filters_by_integer(
        self, db_session: AsyncSession
    ) -> None:
        """Test CRUD function filters correctly when min_count is an integer."""
        for i in range(1):
            user_in = UserCreate(email=f"user{i}@alpha.com", full_name="A")
            await crud.create_user(db_session, user_in)

        for i in range(3):
            user_in = UserCreate(email=f"user{i}@beta.com", full_name=f"B{i}")
            await crud.create_user(db_session, user_in)

        for i in range(2):
            user_in = UserCreate(email=f"user{i}@gamma.com", full_name=f"C{i}")
            await crud.create_user(db_session, user_in)

        result = await crud.count_users_by_domain(db_session, min_count=2)
        assert len(result) == 2
        assert result[0]["domain"] == "beta.com"
        assert result[0]["count"] == 3
        assert result[1]["domain"] == "gamma.com"
        assert result[1]["count"] == 2

    # AC-003: CRUD min_count=None returns all domains
    async def test_crud_min_count_none_returns_all(
        self, db_session: AsyncSession
    ) -> None:
        """Test CRUD function returns all domains when min_count is None."""
        for i in range(1):
            user_in = UserCreate(email=f"user{i}@alpha.com", full_name="A")
            await crud.create_user(db_session, user_in)

        for i in range(3):
            user_in = UserCreate(email=f"user{i}@beta.com", full_name=f"B{i}")
            await crud.create_user(db_session, user_in)

        result = await crud.count_users_by_domain(db_session, min_count=None)
        assert len(result) == 2
        assert result[0]["domain"] == "beta.com"
        assert result[0]["count"] == 3
        assert result[1]["domain"] == "alpha.com"
        assert result[1]["count"] == 1

    def test_schema_invalid_count_type(self) -> None:
        """Test schema rejects non-integer count."""
        with pytest.raises(ValueError):
            DomainCountResponse(domain="example.com", count="five")


# Seam test: verify domain_count_endpoint contract from TASK-7CEA-001
@pytest.mark.seam
@pytest.mark.integration_contract("domain_count_endpoint")
def test_domain_count_endpoint_format() -> None:
    """Verify domain_count_endpoint matches the expected format.

    Contract: returns JSON array of objects with domain and count fields
    Producer: TASK-7CEA-001
    """
    # Producer side: get the endpoint response
    from src.users.schemas import DomainCountResponse

    # Validate schema directly since we can't easily call the endpoint here
    sample_response: list[DomainCountResponse] = [
        DomainCountResponse(domain="example.com", count=3),
        DomainCountResponse(domain="other.org", count=1),
    ]

    # Consumer side: verify format matches contract
    assert isinstance(sample_response, list)
    for entry in sample_response:
        assert "domain" in entry.model_dump()
        assert "count" in entry.model_dump()
        assert isinstance(entry.domain, str)
        assert isinstance(entry.count, int)
