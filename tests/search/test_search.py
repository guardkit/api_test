"""Tests for the search API endpoint."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.search.schemas import SearchResponse
from src.users.models import User


class TestSearchEndpoint:
    """Tests for the search endpoint."""

    @pytest.mark.asyncio
    async def test_search_returns_200_ok(
        self,
        override_get_db: None,
        async_client: AsyncClient,
    ) -> None:
        """Test that GET /search returns 200 OK."""
        response = await async_client.get("/search", params={"name": "test"})
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.asyncio
    async def test_search_accepts_name_query_parameter(
        self,
        override_get_db: None,
        async_client: AsyncClient,
    ) -> None:
        """Test that the search endpoint accepts a name query parameter."""
        response = await async_client.get("/search", params={"name": "myquery"})
        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["query"] == "myquery"

    @pytest.mark.asyncio
    async def test_search_returns_valid_response_model(
        self,
        override_get_db: None,
        async_client: AsyncClient,
    ) -> None:
        """Test that the search endpoint returns a valid SearchResponse."""
        response = await async_client.get("/search", params={"name": "test"})
        body = response.json()
        assert "query" in body
        assert "results" in body
        assert "total" in body
        assert isinstance(body["query"], str)
        assert isinstance(body["results"], list)
        assert isinstance(body["total"], int)

    @pytest.mark.asyncio
    async def test_search_returns_empty_results_by_default(
        self,
        override_get_db: None,
        async_client: AsyncClient,
    ) -> None:
        """Test that the search endpoint returns empty results by default."""
        response = await async_client.get("/search", params={"name": "anything"})
        body = response.json()
        assert body["results"] == []
        assert body["total"] == 0

    @pytest.mark.asyncio
    async def test_search_post_returns_405_method_not_allowed(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test that POST /search returns 405 Method Not Allowed."""
        response = await async_client.post("/search", json={"name": "test"})
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


class TestSearchLogic:
    """Tests for search logic behavior."""

    @pytest.mark.asyncio
    async def test_search_case_insensitive(
        self,
        override_get_db: None,
        db_session: AsyncSession,
        async_client: AsyncClient,
    ) -> None:
        """Test that search matches names case-insensitively."""
        user1 = User(email="alice@test.com", full_name="Alice Smith")
        user2 = User(email="bob@test.com", full_name="Bob Jones")
        db_session.add(user1)
        db_session.add(user2)
        await db_session.commit()

        response = await async_client.get("/search", params={"name": "alice"})
        body = response.json()
        assert body["total"] == 1
        assert "Alice Smith" in body["results"]

        response = await async_client.get("/search", params={"name": "ALICE"})
        body = response.json()
        assert body["total"] == 1
        assert "Alice Smith" in body["results"]

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_all(
        self,
        override_get_db: None,
        db_session: AsyncSession,
        async_client: AsyncClient,
    ) -> None:
        """Test that empty query returns all users."""
        user = User(email="test@test.com", full_name="Test User")
        db_session.add(user)
        await db_session.commit()

        response = await async_client.get("/search", params={"name": ""})
        body = response.json()
        assert body["total"] == 1
        assert "Test User" in body["results"]

    @pytest.mark.asyncio
    async def test_search_whitespace_query_returns_all(
        self,
        override_get_db: None,
        db_session: AsyncSession,
        async_client: AsyncClient,
    ) -> None:
        """Test that whitespace-only query returns all users."""
        user = User(email="test@test.com", full_name="Test User")
        db_session.add(user)
        await db_session.commit()

        response = await async_client.get("/search", params={"name": "   "})
        body = response.json()
        assert body["total"] == 1
        assert "Test User" in body["results"]

    @pytest.mark.asyncio
    async def test_search_special_characters_literal(
        self,
        override_get_db: None,
        db_session: AsyncSession,
        async_client: AsyncClient,
    ) -> None:
        """Test that special characters are treated literally."""
        user1 = User(email="test1@test.com", full_name="100% Complete")
        user2 = User(email="test2@test.com", full_name="Normal User")
        db_session.add(user1)
        db_session.add(user2)
        await db_session.commit()

        response = await async_client.get("/search", params={"name": "100%"})
        body = response.json()
        assert body["total"] == 1
        assert "100% Complete" in body["results"]

        # "%" matches "100% Complete" - proves % is treated literally
        response = await async_client.get("/search", params={"name": "%"})
        body = response.json()
        assert body["total"] == 1
        assert "100% Complete" in body["results"]


class TestSearchSchema:
    """Tests for the SearchResponse schema."""

    def test_search_schema_has_required_fields(self) -> None:
        """Test that SearchResponse has all required fields.

        This is an invariant test: the SearchResponse schema must always
        have query, results, and total fields.
        """
        fields = SearchResponse.model_fields
        assert "query" in fields
        assert "results" in fields
        assert "total" in fields

    def test_search_schema_query_field_description(self) -> None:
        """Test that the query field has a description."""
        fields = SearchResponse.model_fields
        assert fields["query"].description is not None
        assert len(fields["query"].description) > 0

    def test_search_schema_results_field_description(self) -> None:
        """Test that the results field has a description."""
        fields = SearchResponse.model_fields
        assert fields["results"].description is not None
        assert len(fields["results"].description) > 0

    def test_search_schema_total_field_description(self) -> None:
        """Test that the total field has a description."""
        fields = SearchResponse.model_fields
        assert fields["total"].description is not None
        assert len(fields["total"].description) > 0

    def test_search_schema_default_values(self) -> None:
        """Test that SearchResponse has correct default values."""
        schema = SearchResponse(query="test")
        assert schema.query == "test"
        assert schema.results == []
        assert schema.total == 0


class TestSearchRouteRegistered:
    """Tests that the search route is registered in the FastAPI app."""

    def test_search_tag_in_openapi(self) -> None:
        """Test that the search tag is registered in OpenAPI schema.

        This is an invariant test: the search tag must always be present
        in the OpenAPI schema for API documentation.
        """
        from src.main import app

        openapi_schema = app.openapi()
        tags = openapi_schema.get("tags", [])
        tag_names = [tag["name"] for tag in tags]
        assert "search" in tag_names

    def test_search_route_in_openapi_paths(self) -> None:
        """Test that the /search path is registered in OpenAPI schema.

        This is an invariant test: the /search path must always be present
        in the OpenAPI schema for API documentation.
        """
        from src.main import app

        openapi_schema = app.openapi()
        paths = openapi_schema.get("paths", {})
        assert "/search" in paths

    def test_search_get_method_in_openapi(self) -> None:
        """Test that GET /search is registered in OpenAPI schema.

        This is an invariant test: the GET method on /search must always
        be present in the OpenAPI schema for API documentation.
        """
        from src.main import app

        openapi_schema = app.openapi()
        paths = openapi_schema.get("paths", {})
        assert "get" in paths["/search"]

    def test_search_accepts_name_parameter_in_openapi(self) -> None:
        """Test that the name parameter is defined in OpenAPI schema.

        This is an invariant test: the name query parameter must always
        be documented in the OpenAPI schema.
        """
        from src.main import app

        openapi_schema = app.openapi()
        parameters = openapi_schema["paths"]["/search"]["get"].get("parameters", [])
        param_names = [p["name"] for p in parameters]
        assert "name" in param_names
