"""Tests for API documentation completeness and accuracy."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient


@pytest.fixture
def api_docs_path() -> Path:
    """Return the path to the API documentation file."""
    return Path(__file__).parent.parent / "docs" / "API.md"


def test_api_documentation_exists(api_docs_path: Path) -> None:
    """Test that the API documentation file exists.

    AC-001: API documentation updated to include /version endpoint
    """
    assert api_docs_path.exists(), "API.md documentation file must exist"
    assert api_docs_path.is_file(), "API.md must be a file"


def test_api_documentation_contains_version_endpoint(api_docs_path: Path) -> None:
    """Test that the API documentation includes the /version endpoint.

    AC-001: API documentation updated to include /version endpoint
    """
    content = api_docs_path.read_text()

    # Verify endpoint is documented
    assert "/version" in content, "Documentation must include /version endpoint"
    assert "GET /version" in content, "Documentation must specify GET method"

    # Verify key sections are present
    assert "Version Information" in content or "version" in content.lower()
    assert "Response" in content or "response" in content.lower()


def test_api_documentation_contains_example_request(api_docs_path: Path) -> None:
    """Test that the API documentation includes example request.

    AC-002: Example request and response included
    """
    content = api_docs_path.read_text()

    # Verify example request is documented
    assert "Example Request" in content or "example request" in content.lower()
    assert "curl" in content or "GET" in content, (
        "Documentation should include example request using curl or similar"
    )


def test_api_documentation_contains_example_response(api_docs_path: Path) -> None:
    """Test that the API documentation includes example response.

    AC-002: Example request and response included
    """
    content = api_docs_path.read_text()

    # Verify example response is documented
    assert "Example Response" in content or "example response" in content.lower()

    # Verify the response contains the required fields in JSON format
    # The documentation should have a JSON code block with version, commit, service
    assert "version" in content.lower()
    assert "commit" in content.lower()
    assert "service" in content.lower()


def test_api_documentation_response_schema_matches_implementation(
    api_docs_path: Path,
) -> None:
    """Test that documented response schema fields match the actual implementation.

    This validates that the documentation accurately reflects the endpoint behavior.
    """
    content = api_docs_path.read_text()

    # The three required fields from VersionResponse schema
    required_fields = ["version", "commit", "service"]

    for field in required_fields:
        assert field in content, (
            f"Documentation must describe the '{field}' field in the response"
        )


@pytest.mark.asyncio
async def test_documented_example_matches_actual_response_structure(
    async_client: AsyncClient,
    api_docs_path: Path,
) -> None:
    """Test that the documented example response matches actual endpoint structure.

    This is an invariant test: the structure of the /version response
    should always contain exactly the fields version, commit, and service,
    regardless of future tasks that might add more endpoints.
    """
    # Get actual response from the endpoint
    response = await async_client.get("/version")
    actual_data = response.json()

    # Verify the endpoint returns the documented fields
    documented_fields = {"version", "commit", "service"}
    actual_fields = set(actual_data.keys())

    assert actual_fields == documented_fields, (
        f"Endpoint returns fields {actual_fields}, but documentation implies "
        f"{documented_fields}. Documentation and implementation must match."
    )

    # Verify field types match what's documented
    assert isinstance(actual_data["version"], str)
    assert isinstance(actual_data["commit"], str)
    assert isinstance(actual_data["service"], str)


def test_api_documentation_includes_status_codes(api_docs_path: Path) -> None:
    """Test that the documentation includes HTTP status codes.

    Validates that the documentation describes both success and error cases.
    """
    content = api_docs_path.read_text()

    # Should document success case
    assert "200" in content or "OK" in content

    # Should document error cases for unsupported methods
    assert "405" in content or "Method Not Allowed" in content


def test_api_documentation_describes_field_meanings(api_docs_path: Path) -> None:
    """Test that the documentation describes what each response field means.

    Good API documentation explains not just the structure but the meaning.
    """
    content = api_docs_path.read_text()

    # Each field should have some description
    # Looking for patterns like "version" followed by descriptive text
    content_lower = content.lower()

    # The documentation should explain these are build metadata
    assert any(
        keyword in content_lower
        for keyword in ["application version", "app version", "version string"]
    ), "Documentation should describe the version field"

    assert any(keyword in content_lower for keyword in ["git", "commit", "hash"]), (
        "Documentation should describe the commit field"
    )

    assert any(keyword in content_lower for keyword in ["service name", "service"]), (
        "Documentation should describe the service field"
    )
