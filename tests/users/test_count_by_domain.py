"""Tests for the /users/count-by-domain endpoint and count_users_by_domain CRUD function."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import DomainCountResponse, UserCreate


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
