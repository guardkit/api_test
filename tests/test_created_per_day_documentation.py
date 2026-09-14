"""Tests for the GET /users/created-per-day API documentation (TASK-3560-005).

These are documentation-versus-implementation invariants, not snapshots of the
prose: every assertion that names a field, a status code, a window length or an
HTTP method is derived from the running app (`src.main.app`, the OpenAPI schema
and `src.users.schemas.DayCountResponse`), so the docs fail the moment they
drift from the endpoint they describe.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from src.main import app
from src.users.router import CREATED_PER_DAY_WINDOW_DAYS
from src.users.schemas import DayCountResponse

DOCS_PATH = Path(__file__).resolve().parents[1] / "docs" / "API.md"
ENDPOINT_PATH = "/users/created-per-day"
SECTION_HEADING = f"#### GET {ENDPOINT_PATH}"

_FENCE = re.compile(r"```(?P<lang>[A-Za-z]*)\n(?P<body>.*?)\n```", re.DOTALL)
_BOLD_LABEL = re.compile(r"^\*\*(?P<label>[^*]+)\*\*", flags=re.MULTILINE)


@pytest.fixture(scope="module")
def docs_text() -> str:
    """Return the full text of docs/API.md.

    Returns:
        str: The documentation file contents.
    """
    assert DOCS_PATH.is_file(), f"{DOCS_PATH} must exist"
    return DOCS_PATH.read_text(encoding="utf-8")


def _section(docs_text: str) -> str:
    """Return only the created-per-day section of the documentation.

    Args:
        docs_text: The full docs/API.md contents.

    Returns:
        str: The section that starts at the "#### GET /users/created-per-day"
        heading and stops at the horizontal rule closing it.
    """
    start = docs_text.find(SECTION_HEADING)
    assert start != -1, (
        f"docs/API.md must document the endpoint under a '{SECTION_HEADING}' heading"
    )
    tail = docs_text[start + len(SECTION_HEADING) :]
    end = tail.find("\n---\n")
    return docs_text[
        start : start + len(SECTION_HEADING) + (len(tail) if end == -1 else end)
    ]


def _fenced_blocks(section: str) -> list[tuple[str, str, str]]:
    """Return every fenced block in the section.

    Args:
        section: The documentation section text.

    Returns:
        list[tuple[str, str, str]]: One (nearest preceding bold label, language,
        raw body) tuple per fenced code block, in document order.
    """
    blocks: list[tuple[str, str, str]] = []
    cursor = 0
    for match in _FENCE.finditer(section):
        labels = _BOLD_LABEL.findall(section[cursor : match.start()])
        blocks.append(
            (labels[-1] if labels else "", match.group("lang"), match.group("body"))
        )
        cursor = match.end()
    return blocks


def _json_block(section: str, label: str) -> Any:
    """Return the parsed JSON body of the block labelled ``label``.

    Args:
        section: The documentation section text.
        label: Exact bold label of the block to read.

    Returns:
        Any: The decoded JSON payload of that block.
    """
    for block_label, lang, body in _fenced_blocks(section):
        if block_label == label and lang == "json":
            return json.loads(body)
    pytest.fail(f"docs/API.md must include a '**{label}**' JSON block")


def _example_responses(section: str) -> list[tuple[str, Any]]:
    """Return every "**Example Response ...**" JSON block in the section.

    Args:
        section: The documentation section text.

    Returns:
        list[tuple[str, Any]]: (label, decoded payload) per example response.
    """
    return [
        (block_label, json.loads(body))
        for block_label, lang, body in _fenced_blocks(section)
        if lang == "json" and block_label.startswith("Example Response")
    ]


def test_documentation_names_the_endpoint_path_and_method(docs_text: str) -> None:
    """AC-001: the docs carry the endpoint path and its HTTP method."""
    section = _section(docs_text)

    assert ENDPOINT_PATH in section, "Documentation must include the endpoint path"
    assert f"GET {ENDPOINT_PATH}" in section, (
        "Documentation must specify the GET method"
    )


def test_documented_path_and_method_match_the_registered_route(docs_text: str) -> None:
    """AC-001: the documented path/method is the route the app actually serves."""
    section = _section(docs_text)

    path_item = app.openapi()["paths"].get(ENDPOINT_PATH, {})
    served_methods = {method.upper() for method in path_item}
    documented_methods = {
        verb.upper()
        for verb in ("GET", "POST", "PUT", "PATCH", "DELETE")
        if verb in section
    }

    assert served_methods, f"{ENDPOINT_PATH} must be a route the app serves"
    assert documented_methods == served_methods, (
        f"Documented methods {documented_methods} must be the methods served "
        f"on {ENDPOINT_PATH} ({served_methods})"
    )


def test_documentation_describes_the_response_schema_fields(docs_text: str) -> None:
    """AC-002: the response schema names exactly the fields the model returns."""
    section = _section(docs_text)

    schema = _json_block(section, "Response Schema")
    assert isinstance(schema, list), "The response schema must be a JSON array"
    assert len(schema) == 1, "The response schema must show one template array item"
    template = schema[0]
    assert isinstance(template, dict), "Each response-schema item must be an object"
    assert set(template) == set(DayCountResponse.model_fields), (
        "Documented schema fields must match the DayCountResponse model fields"
    )


def test_documentation_describes_the_response_shape_in_prose(docs_text: str) -> None:
    """AC-002: the prose describes the shape the endpoint returns."""
    section = _section(docs_text)
    format_part = section[section.find("**Response Format**") :]

    assert format_part, "Documentation must include a Response Format description"
    assert "array" in format_part.lower(), "Response format must state a JSON array"
    assert f"exactly {CREATED_PER_DAY_WINDOW_DAYS} entries" in format_part, (
        "Response format must state the array length the endpoint returns"
    )
    assert "sorted ascending" in format_part.lower(), (
        "Response format must state the ordering the endpoint returns"
    )
    for field_name in DayCountResponse.model_fields:
        assert f"`{field_name}`" in section, (
            f"Documentation must describe the '{field_name}' response field"
        )


def test_documented_status_codes_cover_the_declared_ones(docs_text: str) -> None:
    """AC-002: every status code the endpoint declares is documented."""
    section = _section(docs_text)
    declared = set(app.openapi()["paths"][ENDPOINT_PATH]["get"]["responses"])

    for status_code in declared:
        assert status_code in section, (
            f"Documentation must document declared status code {status_code}"
        )
    assert "405" in section, "Documentation must document the 405 method rejection"


async def test_documented_response_fields_match_the_live_response(
    async_client: AsyncClient,
    override_get_db: None,
    docs_text: str,
) -> None:
    """AC-002: the documented fields and length match a real endpoint response."""
    section = _section(docs_text)
    documented_fields = set(_json_block(section, "Response Schema")[0])

    response = await async_client.get(ENDPOINT_PATH)

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == CREATED_PER_DAY_WINDOW_DAYS
    for item in payload:
        assert isinstance(item, dict)
        assert set(item) == documented_fields, (
            "The keys the endpoint returns must be the keys the docs describe"
        )


def test_documentation_includes_an_example_request(docs_text: str) -> None:
    """AC-003: the docs show how to call the endpoint."""
    section = _section(docs_text)
    requests = [
        body
        for label, _lang, body in _fenced_blocks(section)
        if label.startswith("Example Request")
    ]

    assert requests, "Documentation must include an example request"
    assert ENDPOINT_PATH in requests[0], (
        "The example request must hit the endpoint path"
    )
    assert "GET" in requests[0].upper(), "The example request must use the GET method"


def test_documentation_includes_example_responses(docs_text: str) -> None:
    """AC-003: the docs include at least one example response."""
    section = _section(docs_text)

    examples = _example_responses(section)
    assert examples, "Documentation must include example responses"
    assert any(
        label.startswith("Example Response (Happy Path") for label, _ in examples
    ), "Documentation must include a happy-path example response"


def test_example_responses_conform_to_the_documented_contract(docs_text: str) -> None:
    """AC-003: each success example is a valid instance of the contract."""
    section = _section(docs_text)
    success = [
        payload
        for label, payload in _example_responses(section)
        if "Error" not in label and isinstance(payload, list)
    ]

    assert success, "Documentation must show at least one successful example response"
    for payload in success:
        assert len(payload) == CREATED_PER_DAY_WINDOW_DAYS, (
            "Example responses must carry the number of data points documented"
        )
        days: list[date] = []
        for entry in payload:
            validated = DayCountResponse.model_validate(entry)
            assert set(entry) == set(DayCountResponse.model_fields), (
                "Example entries must carry exactly the documented fields"
            )
            days.append(validated.date)
        assert days == sorted(days), (
            "Example responses must be ordered oldest day first"
        )
        assert len(set(days)) == len(days), "Example responses must not repeat a day"


def test_error_example_uses_the_common_error_format(docs_text: str) -> None:
    """AC-003: the error example follows the documented error envelope."""
    section = _section(docs_text)
    errors = [
        payload
        for label, payload in _example_responses(section)
        if "Error" in label and isinstance(payload, dict)
    ]

    assert errors, "Documentation must show an error example response"
    for payload in errors:
        assert "detail" in payload, "Error examples must use the shared detail envelope"


def test_documentation_keeps_the_endpoint_inside_the_endpoints_section(
    docs_text: str,
) -> None:
    """The endpoint stays documented under the Endpoints section of docs/API.md."""
    endpoints_at = docs_text.find("\n## Endpoints\n")
    next_major_at = docs_text.find("\n## Common Response Formats\n")

    assert endpoints_at != -1 and next_major_at != -1, (
        "docs/API.md must keep the Endpoints and Common Response Formats sections"
    )
    assert endpoints_at < docs_text.find(SECTION_HEADING) < next_major_at, (
        "The endpoint documentation must live inside the Endpoints section"
    )


def test_documentation_file_stays_well_formed_markdown(docs_text: str) -> None:
    """Format invariant for docs/API.md: balanced fences, clean whitespace.

    The whitespace checks are scoped to the section this task owns; the
    pre-existing Overview block carries trailing spaces this task does not
    touch.
    """
    section = _section(docs_text)

    assert docs_text.count("```") % 2 == 0, (
        "Code fences in docs/API.md must be balanced"
    )
    assert docs_text.endswith("\n"), "docs/API.md must end with a newline"
    assert not any(line.rstrip() != line for line in section.splitlines()), (
        "The endpoint section must not carry trailing whitespace"
    )
    assert "\t" not in section, "The endpoint section must not contain tabs"


def test_documentation_dates_in_examples_are_real_calendar_days(docs_text: str) -> None:
    """AC-003: example dates are parseable ISO 8601 calendar dates."""
    section = _section(docs_text)
    examples = [
        entry
        for _label, payload in _example_responses(section)
        if isinstance(payload, list)
        for entry in payload
        if isinstance(entry, dict)
    ]

    assert examples, "Example responses must show date/count pairs"
    for entry in examples:
        assert isinstance(entry["date"], str)
        assert datetime.strptime(entry["date"], "%Y-%m-%d").date()
