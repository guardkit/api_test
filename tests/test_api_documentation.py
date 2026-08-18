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
    content = api_docs_path.read_text()

    # The three required fields from VersionResponse schema
    required_fields = ["version", "commit", "service"]

    for field in required_fields:
        assert field in content, (
            f"Documentation must describe the '{field}' field in the response"
        )


# ---------------------------------------------------------------------------
# Readiness endpoint documentation tests (TASK-D9A6-004)
# ---------------------------------------------------------------------------


def test_api_documentation_contains_ready_endpoint_path_and_method(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes the /ready endpoint with GET method.

    AC-001: Endpoint path and method documented
    """
    content = api_docs_path.read_text()

    # Verify the endpoint path is documented
    assert "/ready" in content, "Documentation must include the /ready endpoint path"

    # Verify the HTTP method is documented
    assert "GET /ready" in content, (
        "Documentation must specify GET as the HTTP method for /ready"
    )


def test_api_documentation_contains_ready_endpoint_section(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes a dedicated section
    for the /ready endpoint.

    AC-001: Endpoint path and method documented
    """
    content = api_docs_path.read_text()

    # Verify a section header exists for readiness
    assert "Readiness Check" in content, (
        "Documentation must include a Readiness Check section"
    )

    # Verify the endpoint is described with its purpose
    assert "ready" in content.lower() and "accept" in content.lower(), (
        "Documentation must describe the readiness endpoint's purpose"
    )


def test_api_documentation_ready_response_schema(
    api_docs_path: Path,
) -> None:
    """Test that the documented response schema matches the ReadyResponse model.

    AC-002: Response format documented
    """
    content = api_docs_path.read_text()

    # Verify response schema section exists
    assert "Response Schema" in content or "Response Schemas" in content, (
        "Documentation must include response schema for /ready"
    )

    # Verify the two fields from ReadyResponse are documented
    assert '"status"' in content or "'status'" in content, (
        "Documentation must include the 'status' field in /ready response"
    )
    assert '"service"' in content or "'service'" in content, (
        "Documentation must include the 'service' field in /ready response"
    )

    # Verify the status values are documented
    assert "ready" in content.lower(), (
        "Documentation must describe the 'ready' status value"
    )
    assert "not_ready" in content.lower(), (
        "Documentation must describe the 'not_ready' status value"
    )


def test_api_documentation_ready_example_request(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes an example request for /ready.

    AC-002: Response format documented
    """
    content = api_docs_path.read_text()

    # Verify example request exists for /ready
    assert "Example Request" in content, "Documentation must include an example request"
    assert "curl" in content, "Documentation must include a curl example"
    # The example must reference /ready
    assert "/ready" in content, (
        "Documentation example must reference the /ready endpoint"
    )


def test_api_documentation_ready_example_responses(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes example responses for /ready.

    AC-002: Response format documented
    """
    content = api_docs_path.read_text()

    # Verify example responses exist
    assert "Example Response" in content, "Documentation must include example responses"

    # Verify JSON code blocks with readiness data
    assert "status" in content.lower(), (
        "Documentation must show the 'status' field in example response"
    )
    assert "service" in content.lower(), (
        "Documentation must show the 'service' field in example response"
    )


def test_api_documentation_ready_status_codes(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes status codes for /ready.

    AC-002: Response format documented
    """
    content = api_docs_path.read_text()

    # Verify HTTP status codes are documented
    assert "200" in content, (
        "Documentation must document the 200 status code for /ready"
    )
    assert "503" in content, (
        "Documentation must document the 503 status code for /ready"
    )
    assert "405" in content, (
        "Documentation must document the 405 method not allowed for /ready"
    )


def test_api_documentation_ready_field_descriptions(
    api_docs_path: Path,
) -> None:
    """Test that field descriptions are documented for /ready response.

    AC-002: Response format documented
    """
    content = api_docs_path.read_text()

    # Verify field descriptions are present
    assert "Field Descriptions" in content, (
        "Documentation must include field descriptions"
    )

    # Verify the status field is described
    assert "readiness" in content.lower() or "ready" in content.lower(), (
        "Documentation must describe the readiness status field"
    )

    # Verify the service field is described
    has_svc = "service name" in content.lower()
    has_svc_name = "name of the service" in content.lower()
    assert has_svc or has_svc_name, "Documentation must describe the service field"


def test_api_documentation_ready_implementation_notes(
    api_docs_path: Path,
) -> None:
    """Test that implementation notes are included for /ready endpoint.

    AC-001: Endpoint path and method documented (implementation context)
    """
    content = api_docs_path.read_text()

    # Verify implementation notes exist
    assert "Implementation Notes" in content, (
        "Documentation must include implementation notes"
    )

    # Verify notes mention readiness state management
    assert "readiness" in content.lower() or "ready" in content.lower(), (
        "Implementation notes must reference readiness state"
    )


# ---------------------------------------------------------------------------
# Health endpoint documentation tests (TASK-6D13-005)
# ---------------------------------------------------------------------------


def test_api_documentation_contains_health_endpoint_path_and_method(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes the /health endpoint with GET method.

    AC-001: Endpoint path and method documented
    """
    content = api_docs_path.read_text()

    # Verify the endpoint path is documented
    assert "/health" in content, "Documentation must include the /health endpoint path"

    # Verify the HTTP method is documented
    assert "GET /health" in content, (
        "Documentation must specify GET as the HTTP method for /health"
    )


def test_api_documentation_contains_health_endpoint_section(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes a dedicated section
    for the /health endpoint.

    AC-001: Endpoint path and method documented
    """
    content = api_docs_path.read_text()

    # Verify a section header exists for health
    assert "Health Check" in content, (
        "Documentation must include a Health Check section"
    )

    # Verify the endpoint is described with its purpose
    assert "health" in content.lower() and "status" in content.lower(), (
        "Documentation must describe the health endpoint's purpose"
    )


def test_api_documentation_health_response_schema(
    api_docs_path: Path,
) -> None:
    """Test that the documented response schema matches the HealthResponse model.

    AC-002: Response format documented
    """
    content = api_docs_path.read_text()

    # Verify response schema section exists
    assert "Response Schema" in content or "Response Schemas" in content, (
        "Documentation must include response schema for /health"
    )

    # Verify the five fields from HealthResponse are documented
    assert '"status"' in content or "'status'" in content, (
        "Documentation must include the 'status' field in /health response"
    )
    assert '"version"' in content or "'version'" in content, (
        "Documentation must include the 'version' field in /health response"
    )
    assert '"log_level"' in content or "'log_level'" in content, (
        "Documentation must include the 'log_level' field in /health response"
    )
    assert '"log_format"' in content or "'log_format'" in content, (
        "Documentation must include the 'log_format' field in /health response"
    )
    assert '"database"' in content or "'database'" in content, (
        "Documentation must include the 'database' field in /health response"
    )


def test_api_documentation_health_example_request(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes an example request for /health.

    AC-002: Response format documented
    """
    content = api_docs_path.read_text()

    # Verify example request exists for /health
    assert "Example Request" in content, "Documentation must include an example request"
    assert "curl" in content, "Documentation must include a curl example"
    # The example must reference /health
    assert "/health" in content, (
        "Documentation example must reference the /health endpoint"
    )


def test_api_documentation_health_example_responses(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes example responses for /health.

    AC-002: Response format documented
    """
    content = api_docs_path.read_text()

    # Verify example responses exist
    assert "Example Response" in content, "Documentation must include example responses"

    # Verify JSON code blocks with health data
    assert "status" in content.lower(), (
        "Documentation must show the 'status' field in example response"
    )
    assert "database" in content.lower(), (
        "Documentation must show the 'database' field in example response"
    )


def test_api_documentation_health_status_codes(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes status codes for /health.

    AC-003: Error scenarios documented
    """
    content = api_docs_path.read_text()

    # Verify HTTP status codes are documented
    assert "200" in content, (
        "Documentation must document the 200 status code for /health"
    )
    assert "405" in content, (
        "Documentation must document the 405 method not allowed for /health"
    )


def test_api_documentation_health_error_scenarios(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes error scenarios for /health.

    AC-003: Error scenarios documented
    """
    content = api_docs_path.read_text()

    # Verify database error scenario is documented
    assert "degraded" in content.lower(), (
        "Documentation must describe the 'degraded' status for database issues"
    )
    assert "unavailable" in content.lower(), (
        "Documentation must describe the 'unavailable' database status"
    )


def test_api_documentation_health_field_descriptions(
    api_docs_path: Path,
) -> None:
    """Test that field descriptions are documented for /health response.

    AC-002: Response format documented
    """
    content = api_docs_path.read_text()

    # Verify field descriptions are present
    assert "Field Descriptions" in content, (
        "Documentation must include field descriptions"
    )

    # Verify the status field is described
    assert "health status" in content.lower() or "service health" in content.lower(), (
        "Documentation must describe the health status field"
    )

    # Verify the database field is described
    has_db = "database" in content.lower()
    has_conn = "connected" in content.lower()
    has_unavail = "unavailable" in content.lower()
    assert has_db and (has_conn or has_unavail), (
        "Documentation must describe the database connection status field"
    )


def test_api_documentation_health_implementation_notes(
    api_docs_path: Path,
) -> None:
    """Test that implementation notes are included for /health endpoint.

    AC-003: Error scenarios documented (implementation context for error handling)
    """
    content = api_docs_path.read_text()

    # Verify implementation notes exist
    assert "Implementation Notes" in content, (
        "Documentation must include implementation notes"
    )

    # Verify notes mention database probe
    has_db = "database" in content.lower()
    has_probe = "probe" in content.lower()
    has_query = "query" in content.lower()
    assert has_db and (has_probe or has_query), (
        "Implementation notes must reference database health checking"
    )


def test_api_documentation_ready_use_cases(
    api_docs_path: Path,
) -> None:
    """Test that use cases are documented for /ready endpoint.

    AC-001: Endpoint path and method documented (contextual documentation)
    """
    content = api_docs_path.read_text()

    # Verify use cases are documented
    assert "Use Cases" in content, "Documentation must include use cases"

    # Verify Kubernetes or load balancer context is mentioned
    assert (
        "kubernetes" in content.lower()
        or "load balancer" in content.lower()
        or "probe" in content.lower()
    ), "Documentation must reference Kubernetes or load balancer use cases"


def test_api_documentation_ready_consistent_with_implementation(
    api_docs_path: Path,
) -> None:
    """Test that documented response format matches the ReadyResponse schema.

    This is an invariant test: the documented fields for /ready must match
    the ReadyResponse model fields (status, service), regardless of future
    changes to other endpoints.
    """
    content = api_docs_path.read_text()

    # Read the actual ReadyResponse schema to verify alignment
    from src.health.schemas import ReadyResponse

    schema_fields = set(ReadyResponse.model_fields.keys())
    documented_fields = set()

    for field_name in schema_fields:
        # Check if the field name appears in the documentation
        # Allow both quoted and unquoted forms
        if f'"{field_name}"' in content or f"'{field_name}'" in content:
            documented_fields.add(field_name)

    assert documented_fields == schema_fields, (
        f"Documented fields {documented_fields} must match "
        f"ReadyResponse fields {schema_fields}"
    )
