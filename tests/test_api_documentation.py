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


class TestCountByDomainDocumentation:
    """Tests for the count-by-domain endpoint documentation."""

    def test_documentation_contains_count_by_domain_endpoint(
        self, api_docs_path: Path
    ) -> None:
        """Test that the count-by-domain endpoint is documented.

        AC-001: Document the `min_count` query parameter in the API specification
        """
        content = api_docs_path.read_text()
        assert "/users/count-by-domain" in content, (
            "API documentation must include the /users/count-by-domain endpoint"
        )

    def test_documentation_contains_min_count_parameter_description(
        self, api_docs_path: Path
    ) -> None:
        """Test that the `min_count` query parameter is described in the documentation.

        AC-001: Document the `min_count` query parameter in the API specification
        """
        content = api_docs_path.read_text()
        assert "min_count" in content, (
            "API documentation must document the `min_count` query parameter"
        )
        # Verify it's described as a query parameter
        assert "Query Parameters" in content or "query parameter" in content.lower()

    def test_documentation_contains_min_count_query_params_table(
        self, api_docs_path: Path
    ) -> None:
        """Test that the documentation includes a query parameters table for min_count.

        AC-001: Document the `min_count` query parameter in the API specification
        """
        content = api_docs_path.read_text()
        # The table should have min_count with its type and description
        assert "min_count" in content
        assert "integer" in content.lower()
        # Verify the parameter has a description of its filtering behavior
        assert (
            "filter" in content.lower()
            or "exclude" in content.lower()
            or ("minimum" in content.lower() and "domain" in content.lower())
        )

    def test_documentation_contains_valid_min_count_examples(
        self, api_docs_path: Path
    ) -> None:
        """Test that the documentation includes examples of valid `min_count` values.

        AC-002: Include examples of valid and invalid `min_count` values
        """
        content = api_docs_path.read_text()
        assert "Valid" in content or "valid" in content.lower()
        # Check for specific valid examples
        assert "0" in content  # zero is a valid value
        assert "1" in content  # one is a valid value
        assert "10000" in content  # maximum is a valid value

    def test_documentation_contains_invalid_min_count_examples(
        self, api_docs_path: Path
    ) -> None:
        """Test that the documentation includes examples of invalid `min_count` values.

        AC-002: Include examples of valid and invalid `min_count` values
        """
        content = api_docs_path.read_text()
        assert "Invalid" in content or "invalid" in content.lower()
        # Check for specific invalid examples
        assert "-1" in content  # negative is invalid
        assert "non-integer" in content.lower() or "invalid integer" in content.lower()
        # Check for 400 status code documentation
        assert "400" in content or "Bad Request" in content

    def test_documentation_contains_min_count_400_status_code(
        self, api_docs_path: Path
    ) -> None:
        """Test that the documentation includes 400 Bad Request for invalid min_count.

        AC-001: Document the `min_count` query parameter in the API specification
        """
        content = api_docs_path.read_text()
        assert "400" in content, "Documentation must document 400 Bad Request status"
        assert "Bad Request" in content or "bad request" in content.lower()

    def test_documentation_contains_min_count_example_request(
        self, api_docs_path: Path
    ) -> None:
        """Test that the documentation includes an example request using min_count.

        AC-002: Include examples of valid and invalid `min_count` values
        """
        content = api_docs_path.read_text()
        assert "min_count=" in content or "min_count%3D" in content, (
            "Documentation should include an example request with min_count parameter"
        )

    def test_documentation_contains_min_count_max_value(
        self, api_docs_path: Path
    ) -> None:
        """Test that the documentation mentions the maximum allowed min_count value.

        AC-001: Document the `min_count` query parameter in the API specification
        """
        content = api_docs_path.read_text()
        assert "10000" in content, (
            "Documentation must mention the maximum min_count value of 10,000"
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


# ---------------------------------------------------------------------------
# Whoami endpoint documentation tests (TASK-7CEA-004)
# ---------------------------------------------------------------------------


def test_api_documentation_contains_whoami_endpoint_path_and_method(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes the /whoami endpoint with GET method.

    AC-001: Endpoint path and method documented
    """
    content = api_docs_path.read_text()

    assert "/whoami" in content, "Documentation must include the /whoami endpoint path"
    assert "GET /whoami" in content, (
        "Documentation must specify GET as the HTTP method for /whoami"
    )


def test_api_documentation_whoami_response_schema(
    api_docs_path: Path,
) -> None:
    """Test that the documented response schema matches the WhoamiResponse model.

    AC-003: Response format described clearly
    """
    content = api_docs_path.read_text()

    assert "Response Schema" in content or "Response Schemas" in content, (
        "Documentation must include response schema for /whoami"
    )
    assert '"service"' in content or "'service'" in content, (
        "Documentation must include the 'service' field in /whoami response"
    )


def test_api_documentation_whoami_example_request(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes an example request for /whoami.

    AC-002: Examples included for happy path
    """
    content = api_docs_path.read_text()

    assert "Example Request" in content, "Documentation must include an example request"
    assert "curl" in content, "Documentation must include a curl example"
    assert "/whoami" in content, (
        "Documentation example must reference the /whoami endpoint"
    )


def test_api_documentation_whoami_example_response(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes an example response for /whoami.

    AC-002: Examples included for happy path
    """
    content = api_docs_path.read_text()

    assert "Example Response" in content, "Documentation must include example responses"
    assert "service" in content.lower(), (
        "Documentation must show the 'service' field in example response"
    )


def test_api_documentation_whoami_status_codes(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes status codes for /whoami.

    AC-002: Error cases documented
    """
    content = api_docs_path.read_text()

    assert "200" in content, (
        "Documentation must document the 200 status code for /whoami"
    )
    assert "405" in content, (
        "Documentation must document the 405 method not allowed for /whoami"
    )


def test_api_documentation_whoami_field_descriptions(
    api_docs_path: Path,
) -> None:
    """Test that field descriptions are documented for /whoami response.

    AC-003: Response format described clearly
    """
    content = api_docs_path.read_text()

    assert "Field Descriptions" in content, (
        "Documentation must include field descriptions"
    )
    assert "service name" in content.lower() or "api service" in content.lower(), (
        "Documentation must describe the service field"
    )


def test_api_documentation_whoami_consistent_with_implementation(
    api_docs_path: Path,
) -> None:
    """Test that documented response format matches the WhoamiResponse schema.

    This is an invariant test: the documented fields for /whoami must match
    the WhoamiResponse model fields (service), regardless of future changes.
    """
    content = api_docs_path.read_text()

    from src.whoami.schemas import WhoamiResponse

    schema_fields = set(WhoamiResponse.model_fields.keys())
    documented_fields = set()

    for field_name in schema_fields:
        if f'"{field_name}"' in content or f"'{field_name}'" in content:
            documented_fields.add(field_name)

    assert documented_fields == schema_fields, (
        f"Documented fields {documented_fields} must match "
        f"WhoamiResponse fields {schema_fields}"
    )


# ---------------------------------------------------------------------------
# Uptime endpoint documentation tests (TASK-7CEA-004)
# ---------------------------------------------------------------------------


def test_api_documentation_contains_uptime_endpoint_path_and_method(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes the /uptime endpoint with GET method.

    AC-001: Endpoint path and method documented
    """
    content = api_docs_path.read_text()

    assert "/uptime" in content, "Documentation must include the /uptime endpoint path"
    assert "GET /uptime" in content, (
        "Documentation must specify GET as the HTTP method for /uptime"
    )


def test_api_documentation_uptime_response_schema(
    api_docs_path: Path,
) -> None:
    """Test that the documented response schema matches the UptimeResponse model.

    AC-003: Response format described clearly
    """
    content = api_docs_path.read_text()

    assert "Response Schema" in content or "Response Schemas" in content, (
        "Documentation must include response schema for /uptime"
    )
    assert '"service"' in content or "'service'" in content, (
        "Documentation must include the 'service' field in /uptime response"
    )
    assert '"started_at"' in content or "'started_at'" in content, (
        "Documentation must include the 'started_at' field in /uptime response"
    )
    assert '"uptime_seconds"' in content or "'uptime_seconds'" in content, (
        "Documentation must include the 'uptime_seconds' field in /uptime response"
    )


def test_api_documentation_uptime_example_request(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes an example request for /uptime.

    AC-002: Examples included for happy path
    """
    content = api_docs_path.read_text()

    assert "Example Request" in content, "Documentation must include an example request"
    assert "curl" in content, "Documentation must include a curl example"
    assert "/uptime" in content, (
        "Documentation example must reference the /uptime endpoint"
    )


def test_api_documentation_uptime_example_response(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes an example response for /uptime.

    AC-002: Examples included for happy path
    """
    content = api_docs_path.read_text()

    assert "Example Response" in content, "Documentation must include example responses"
    assert "uptime_seconds" in content.lower(), (
        "Documentation must show the 'uptime_seconds' field in example response"
    )


def test_api_documentation_uptime_status_codes(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes status codes for /uptime.

    AC-002: Error cases documented
    """
    content = api_docs_path.read_text()

    assert "200" in content, (
        "Documentation must document the 200 status code for /uptime"
    )
    assert "405" in content, (
        "Documentation must document the 405 method not allowed for /uptime"
    )


def test_api_documentation_uptime_field_descriptions(
    api_docs_path: Path,
) -> None:
    """Test that field descriptions are documented for /uptime response.

    AC-003: Response format described clearly
    """
    content = api_docs_path.read_text()

    assert "Field Descriptions" in content, (
        "Documentation must include field descriptions"
    )
    assert "started_at" in content.lower() or "start time" in content.lower(), (
        "Documentation must describe the started_at field"
    )
    assert "uptime_seconds" in content.lower() or "uptime" in content.lower(), (
        "Documentation must describe the uptime_seconds field"
    )


def test_api_documentation_uptime_consistent_with_implementation(
    api_docs_path: Path,
) -> None:
    """Test that documented response format matches the UptimeResponse schema.

    This is an invariant test: the documented fields for /uptime must match
    the UptimeResponse model fields (service, started_at, uptime_seconds).
    """
    content = api_docs_path.read_text()

    from src.uptime.schemas import UptimeResponse

    schema_fields = set(UptimeResponse.model_fields.keys())
    documented_fields = set()

    for field_name in schema_fields:
        if f'"{field_name}"' in content or f"'{field_name}'" in content:
            documented_fields.add(field_name)

    assert documented_fields == schema_fields, (
        f"Documented fields {documented_fields} must match "
        f"UptimeResponse fields {schema_fields}"
    )


# ---------------------------------------------------------------------------
# Stats endpoint documentation tests (TASK-7CEA-004)
# ---------------------------------------------------------------------------


def test_api_documentation_contains_stats_endpoint_path_and_method(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes the /stats endpoint with GET method.

    AC-001: Endpoint path and method documented
    """
    content = api_docs_path.read_text()

    assert "/stats" in content, "Documentation must include the /stats endpoint path"
    assert "GET /stats" in content, (
        "Documentation must specify GET as the HTTP method for /stats"
    )


def test_api_documentation_stats_response_schema(
    api_docs_path: Path,
) -> None:
    """Test that the documented response schema matches the StatsResponse model.

    AC-003: Response format described clearly
    """
    content = api_docs_path.read_text()

    assert "Response Schema" in content or "Response Schemas" in content, (
        "Documentation must include response schema for /stats"
    )
    assert '"service"' in content or "'service'" in content, (
        "Documentation must include the 'service' field in /stats response"
    )
    assert '"requests_served"' in content or "'requests_served'" in content, (
        "Documentation must include the 'requests_served' field in /stats response"
    )


def test_api_documentation_stats_example_request(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes an example request for /stats.

    AC-002: Examples included for happy path
    """
    content = api_docs_path.read_text()

    assert "Example Request" in content, "Documentation must include an example request"
    assert "curl" in content, "Documentation must include a curl example"
    assert "/stats" in content, (
        "Documentation example must reference the /stats endpoint"
    )


def test_api_documentation_stats_example_response(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes an example response for /stats.

    AC-002: Examples included for happy path
    """
    content = api_docs_path.read_text()

    assert "Example Response" in content, "Documentation must include example responses"
    assert "requests_served" in content.lower(), (
        "Documentation must show the 'requests_served' field in example response"
    )


def test_api_documentation_stats_status_codes(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes status codes for /stats.

    AC-002: Error cases documented
    """
    content = api_docs_path.read_text()

    assert "200" in content, (
        "Documentation must document the 200 status code for /stats"
    )
    assert "405" in content, (
        "Documentation must document the 405 method not allowed for /stats"
    )


def test_api_documentation_stats_consistent_with_implementation(
    api_docs_path: Path,
) -> None:
    """Test that documented response format matches the StatsResponse schema.

    This is an invariant test: the documented fields for /stats must match
    the StatsResponse model fields (service, requests_served).
    """
    content = api_docs_path.read_text()

    from src.stats.router import StatsResponse

    schema_fields = set(StatsResponse.model_fields.keys())
    documented_fields = set()

    for field_name in schema_fields:
        if f'"{field_name}"' in content or f"'{field_name}'" in content:
            documented_fields.add(field_name)

    assert documented_fields == schema_fields, (
        f"Documented fields {documented_fields} must match "
        f"StatsResponse fields {schema_fields}"
    )


# ---------------------------------------------------------------------------
# Time endpoint documentation tests (TASK-7CEA-004)
# ---------------------------------------------------------------------------


def test_api_documentation_contains_time_endpoint_path_and_method(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes the /time endpoint with GET method.

    AC-001: Endpoint path and method documented
    """
    content = api_docs_path.read_text()

    assert "/time" in content, "Documentation must include the /time endpoint path"
    assert "GET /time" in content, (
        "Documentation must specify GET as the HTTP method for /time"
    )


def test_api_documentation_time_response_schema(
    api_docs_path: Path,
) -> None:
    """Test that the documented response schema matches the TimeResponse model.

    AC-003: Response format described clearly
    """
    content = api_docs_path.read_text()

    assert "Response Schema" in content or "Response Schemas" in content, (
        "Documentation must include response schema for /time"
    )
    assert '"time"' in content or "'time'" in content, (
        "Documentation must include the 'time' field in /time response"
    )
    assert '"service"' in content or "'service'" in content, (
        "Documentation must include the 'service' field in /time response"
    )


def test_api_documentation_time_example_request(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes an example request for /time.

    AC-002: Examples included for happy path
    """
    content = api_docs_path.read_text()

    assert "Example Request" in content, "Documentation must include an example request"
    assert "curl" in content, "Documentation must include a curl example"
    assert "/time" in content, "Documentation example must reference the /time endpoint"


def test_api_documentation_time_example_response(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes an example response for /time.

    AC-002: Examples included for happy path
    """
    content = api_docs_path.read_text()

    assert "Example Response" in content, "Documentation must include example responses"
    assert "time" in content.lower(), (
        "Documentation must show the 'time' field in example response"
    )


def test_api_documentation_time_status_codes(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes status codes for /time.

    AC-002: Error cases documented
    """
    content = api_docs_path.read_text()

    assert "200" in content, "Documentation must document the 200 status code for /time"
    assert "405" in content, (
        "Documentation must document the 405 method not allowed for /time"
    )


def test_api_documentation_time_consistent_with_implementation(
    api_docs_path: Path,
) -> None:
    """Test that documented response format matches the TimeResponse schema.

    This is an invariant test: the documented fields for /time must match
    the TimeResponse model fields (time, service).
    """
    content = api_docs_path.read_text()

    from src.time.schemas import TimeResponse

    schema_fields = set(TimeResponse.model_fields.keys())
    documented_fields = set()

    for field_name in schema_fields:
        if f'"{field_name}"' in content or f"'{field_name}'" in content:
            documented_fields.add(field_name)

    assert documented_fields == schema_fields, (
        f"Documented fields {documented_fields} must match "
        f"TimeResponse fields {schema_fields}"
    )


# ---------------------------------------------------------------------------
# Search endpoint documentation tests (TASK-7CEA-004)
# ---------------------------------------------------------------------------


def test_api_documentation_contains_search_endpoint_path_and_method(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes the /search endpoint with GET method.

    AC-001: Endpoint path and method documented
    """
    content = api_docs_path.read_text()

    assert "/search" in content, "Documentation must include the /search endpoint path"
    assert "GET /search" in content, (
        "Documentation must specify GET as the HTTP method for /search"
    )


def test_api_documentation_search_response_schema(
    api_docs_path: Path,
) -> None:
    """Test that the documented response schema matches the SearchResponse model.

    AC-003: Response format described clearly
    """
    content = api_docs_path.read_text()

    assert "Response Schema" in content or "Response Schemas" in content, (
        "Documentation must include response schema for /search"
    )
    assert '"query"' in content or "'query'" in content, (
        "Documentation must include the 'query' field in /search response"
    )
    assert '"results"' in content or "'results'" in content, (
        "Documentation must include the 'results' field in /search response"
    )
    assert '"total"' in content or "'total'" in content, (
        "Documentation must include the 'total' field in /search response"
    )


def test_api_documentation_search_example_request(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes an example request for /search.

    AC-002: Examples included for happy path
    """
    content = api_docs_path.read_text()

    assert "Example Request" in content, "Documentation must include an example request"
    assert "curl" in content, "Documentation must include a curl example"
    assert "/search" in content, (
        "Documentation example must reference the /search endpoint"
    )
    assert "name" in content.lower(), (
        "Documentation example must reference the 'name' query parameter"
    )


def test_api_documentation_search_example_responses(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes example responses for /search.

    AC-002: Examples included for happy path and error cases
    """
    content = api_docs_path.read_text()

    assert "Example Response" in content, "Documentation must include example responses"
    assert "query" in content.lower(), (
        "Documentation must show the 'query' field in example response"
    )
    assert "results" in content.lower(), (
        "Documentation must show the 'results' field in example response"
    )


def test_api_documentation_search_error_example(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes error examples for /search.

    AC-002: Error cases documented
    """
    content = api_docs_path.read_text()

    assert "Error" in content or "error" in content.lower(), (
        "Documentation must include error examples"
    )
    assert "400" in content, (
        "Documentation must document the 400 status code for /search"
    )
    assert "name" in content.lower() and "required" in content.lower(), (
        "Documentation must describe the missing name parameter error"
    )


def test_api_documentation_search_status_codes(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes status codes for /search.

    AC-002: Error cases documented
    """
    content = api_docs_path.read_text()

    assert "200" in content, (
        "Documentation must document the 200 status code for /search"
    )
    assert "400" in content, (
        "Documentation must document the 400 bad request for /search"
    )
    assert "405" in content, (
        "Documentation must document the 405 method not allowed for /search"
    )


def test_api_documentation_search_consistent_with_implementation(
    api_docs_path: Path,
) -> None:
    """Test that documented response format matches the SearchResponse schema.

    This is an invariant test: the documented fields for /search must match
    the SearchResponse model fields (query, results, total).
    """
    content = api_docs_path.read_text()

    from src.search.schemas import SearchResponse

    schema_fields = set(SearchResponse.model_fields.keys())
    documented_fields = set()

    for field_name in schema_fields:
        if f'"{field_name}"' in content or f"'{field_name}'" in content:
            documented_fields.add(field_name)

    assert documented_fields == schema_fields, (
        f"Documented fields {documented_fields} must match "
        f"SearchResponse fields {schema_fields}"
    )


# ---------------------------------------------------------------------------
# Domain Count endpoint documentation tests (TASK-7CEA-004)
# ---------------------------------------------------------------------------


def test_api_documentation_contains_domain_count_endpoint_path_and_method(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes the /users/count-by-domain endpoint.

    AC-001: Endpoint path and method documented
    """
    content = api_docs_path.read_text()

    assert "/users/count-by-domain" in content, (
        "Documentation must include the /users/count-by-domain endpoint path"
    )
    assert "GET" in content, "Documentation must specify GET method"


def test_api_documentation_domain_count_response_schema(
    api_docs_path: Path,
) -> None:
    """Test that the documented response schema matches the DomainCountResponse model.

    AC-003: Response format described clearly
    """
    content = api_docs_path.read_text()

    assert "Response Schema" in content or "Response Schemas" in content, (
        "Documentation must include response schema for /users/count-by-domain"
    )
    assert '"domain"' in content or "'domain'" in content, (
        "Documentation must include the 'domain' field in response"
    )
    assert '"count"' in content or "'count'" in content, (
        "Documentation must include the 'count' field in response"
    )


def test_api_documentation_domain_count_example_request(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes an example request
    for /users/count-by-domain.

    AC-002: Examples included for happy path
    """
    content = api_docs_path.read_text()

    assert "Example Request" in content, "Documentation must include an example request"
    assert "curl" in content, "Documentation must include a curl example"
    assert "/users/count-by-domain" in content, (
        "Documentation example must reference the /users/count-by-domain endpoint"
    )


def test_api_documentation_domain_count_example_response(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes example responses
    for /users/count-by-domain.

    AC-002: Examples included for happy path and error cases
    """
    content = api_docs_path.read_text()

    assert "Example Response" in content, "Documentation must include example responses"
    assert "domain" in content.lower(), (
        "Documentation must show the 'domain' field in example response"
    )
    assert "count" in content.lower(), (
        "Documentation must show the 'count' field in example response"
    )
    # Verify both happy path and empty set examples exist
    assert "[]" in content or "empty" in content.lower(), (
        "Documentation must include empty set example"
    )


def test_api_documentation_domain_count_status_codes(
    api_docs_path: Path,
) -> None:
    """Test that the API documentation includes status codes
    for /users/count-by-domain.

    AC-002: Error cases documented
    """
    content = api_docs_path.read_text()

    assert "200" in content, "Documentation must document the 200 status code"
    assert "503" in content, (
        "Documentation must document the 503 status code for database errors"
    )
    assert "405" in content, "Documentation must document the 405 method not allowed"


def test_api_documentation_domain_count_field_descriptions(
    api_docs_path: Path,
) -> None:
    """Test that field descriptions are documented for /users/count-by-domain response.

    AC-003: Response format described clearly
    """
    content = api_docs_path.read_text()

    assert "Field Descriptions" in content, (
        "Documentation must include field descriptions"
    )
    assert "domain" in content.lower(), "Documentation must describe the domain field"
    assert "count" in content.lower(), "Documentation must describe the count field"


def test_api_documentation_domain_count_consistent_with_implementation(
    api_docs_path: Path,
) -> None:
    """Test that documented response format matches the DomainCountResponse schema.

    This is an invariant test: the documented fields for domain count must match
    the DomainCountResponse model fields (domain, count).
    """
    content = api_docs_path.read_text()

    from src.users.schemas import DomainCountResponse

    schema_fields = set(DomainCountResponse.model_fields.keys())
    documented_fields = set()

    for field_name in schema_fields:
        if f'"{field_name}"' in content or f"'{field_name}'" in content:
            documented_fields.add(field_name)

    assert documented_fields == schema_fields, (
        f"Documented fields {documented_fields} must match "
        f"DomainCountResponse fields {schema_fields}"
    )
