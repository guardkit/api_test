"""Tests for the search API endpoint."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient

from src.search.schemas import SearchResponse


class TestSearchEndpoint:
    """Tests for the search endpoint."""

    @pytest.mark.asyncio
    async def test_search_returns_200_ok(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test that GET /search returns 200 OK.

        This is an invariant test: the /search endpoint must always return
        200 OK for valid requests with a name query parameter, regardless
        of other features or configuration changes.
        """
        response = await async_client.get("/search", params={"name": "test"})

        assert response.status_code == HTTPStatus.OK

    @pytest.mark.asyncio
    async def test_search_accepts_name_query_parameter(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test that the search endpoint accepts a name query parameter.

        This is an invariant test: the /search endpoint must always accept
        the name query parameter, as it is the core search input.
        """
        response = await async_client.get("/search", params={"name": "myquery"})

        assert response.status_code == HTTPStatus.OK

        body = response.json()
        assert body["query"] == "myquery"

    @pytest.mark.asyncio
    async def test_search_returns_valid_response_model(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test that the search endpoint returns a valid SearchResponse.

        This is an invariant test: the /search endpoint must always return
        a response matching the SearchResponse schema (query, results, total).
        """
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
        async_client: AsyncClient,
    ) -> None:
        """Test that the search endpoint returns empty results by default.

        This is an invariant test: the /search endpoint must always return
        an empty results list and zero total count when no implementation
        of search logic is present.
        """
        response = await async_client.get("/search", params={"name": "anything"})

        body = response.json()
        assert body["results"] == []
        assert body["total"] == 0

    @pytest.mark.asyncio
    async def test_search_post_returns_405_method_not_allowed(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test that POST /search returns 405 Method Not Allowed.

        This is an invariant test: the /search endpoint must never accept
        POST requests, as it is a read-only query endpoint.
        """
        response = await async_client.post("/search", json={"name": "test"})

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


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
