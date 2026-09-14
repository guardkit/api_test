"""Documentation tests for ``GET /users/created-per-day`` (TASK-54E1-005).

The point of these tests is not that the words exist somewhere in
``docs/API.md`` — it is that the published description of this endpoint cannot
drift away from the endpoint. Each check compares the document against a
machine-readable authority that already exists:

* AC-001 — the path and method the document names are the path and method the
  application actually routes (``app.openapi()``), and the document states the
  refusal of every other method.
* AC-002 — the fields the document's schema block lists are the fields
  ``src/users/schemas.py``'s ``DailyCountResponse`` declares and the fields the
  OpenAPI component for this operation publishes; every one of them is
  described in prose, and every documented example passes through the model.
* AC-003 — the example request targets the documented path with curl, and the
  example responses are shaped exactly like the responses the running endpoint
  produces, including the 405 refusal body and the single 503 body from
  ``src/core/exceptions.py``.
* AC-004 — the files this task touched pass the project's own checks: ruff for
  Python (``pyproject.toml``, ``[tool.ruff]``) and the document's own markdown
  conventions for the edited section.

Nothing here is a snapshot of the current wording: change the route, the
response model, the error message or the example, and the matching test fails.

Owned elsewhere in FEAT-54E1, deliberately not re-pinned here: the SQL query
and its day bucketing (TASK-54E1-001,
``tests/users/test_created_per_day_counts.py``), the endpoint and its
registration (TASK-54E1-002, ``src/users/router.py``), the seven ordered data
points and the non-GET refusal as runtime behaviour (TASK-54E1-003,
``tests/users/test_daily_counts.py``), and the 503 error-handling surface
(TASK-54E1-004, ``tests/users/test_created_per_day_errors.py``). This file
only asserts that the documentation agrees with those.

These tests read no environment variables, so no outcome depends on the host
environment: which database the run talks to is settled once for the whole
suite in ``tests/__init__.py`` and reaches the endpoint through the
``db_session`` and ``override_get_db`` fixtures in ``tests/conftest.py``.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError

from src.core.exceptions import DatabaseUnavailableError, error_body
from src.main import app
from src.users import crud
from src.users.schemas import DailyCountResponse

ENDPOINT = "/users/created-per-day"

# The window the endpoint promises in its contract: today and the six days
# before it, oldest first. Same constant the endpoint tests use.
WINDOW_DAYS = 7

API_DOCS = Path(__file__).resolve().parents[2] / "docs" / "API.md"

SECTION_HEADING = "### Daily User Creation Counts"

# A fenced block, its language tag and its body.
_FENCE = re.compile(r"```([A-Za-z]*)\n(.*?)\n```", re.DOTALL)

# The error path forced in the documented-503 check: what the driver says when
# the database cannot be reached.
DRIVER_MESSAGE = (
    'connection to server at "db.internal", port 5432 failed: Connection refused'
)


def _docs_text() -> str:
    """Return the text of the published API documentation.

    Returns:
        str: The whole of ``docs/API.md``.

    Raises:
        AssertionError: When the documentation file is missing.
    """
    assert API_DOCS.is_file(), f"{API_DOCS} must exist"
    return API_DOCS.read_text(encoding="utf-8")


def _endpoint_section() -> str:
    """Return the documentation section for this endpoint only.

    A single section keeps every check below about the endpoint this task
    documents, rather than about any text in the file.

    Returns:
        str: The section, from its ``###`` heading up to the next heading.
    """
    text = _docs_text()
    assert SECTION_HEADING in text, (
        f"docs/API.md must contain a '{SECTION_HEADING}' section"
    )
    start = text.index(SECTION_HEADING)
    after_heading = text[start + len(SECTION_HEADING) :]
    ends = [
        index
        for index in (after_heading.find("\n### "), after_heading.find("\n## "))
        if index != -1
    ]
    if not ends:
        return text[start:]
    return text[start : start + len(SECTION_HEADING) + min(ends)]


def _labelled_blocks(section: str, label_prefix: str) -> list[tuple[str, str]]:
    """Return the fenced blocks that follow a bold label in the section.

    Args:
        section: The endpoint's documentation section.
        label_prefix: The label's leading text without its opening ``**``,
            e.g. ``"Example Response"``.

    Returns:
        list[tuple[str, str]]: ``(label line, block body)`` per labelled block,
            in document order.
    """
    lines = section.splitlines()
    blocks: list[tuple[str, str]] = []
    for index, line in enumerate(lines):
        if not line.startswith(f"**{label_prefix}") or not line.rstrip().endswith(
            "**:"
        ):
            continue
        match = _FENCE.search("\n".join(lines[index:]))
        assert match is not None, f"'{line.strip()}' must be followed by a code block"
        blocks.append((line.strip(), match.group(2)))
    return blocks


def _data_point_examples(section: str) -> list[tuple[str, list[dict[str, object]]]]:
    """Return the example responses that are arrays of data points.

    Args:
        section: The endpoint's documentation section.

    Returns:
        list[tuple[str, list[dict[str, object]]]]: ``(label, points)`` for each
            example response body that decodes to a JSON array.
    """
    examples: list[tuple[str, list[dict[str, object]]]] = []
    for label, body in _labelled_blocks(section, "Example Response"):
        parsed = json.loads(body)
        if isinstance(parsed, list):
            examples.append((label, [dict(point) for point in parsed]))
    return examples


def _error_example(section: str, status_marker: str) -> dict[str, object]:
    """Return the documented error body carrying a status marker in its label.

    Args:
        section: The endpoint's documentation section.
        status_marker: The status text the label names, e.g. ``"405"``.

    Returns:
        dict[str, object]: The decoded error body.
    """
    matches = [
        json.loads(body)
        for label, body in _labelled_blocks(section, "Example Response")
        if status_marker in label
    ]
    assert len(matches) == 1, (
        f"exactly one example response labelled with {status_marker} is expected"
    )
    decoded = matches[0]
    assert isinstance(decoded, dict), (
        f"the {status_marker} example must be a JSON object"
    )
    return decoded


def _example_points(section: str) -> list[dict[str, object]]:
    """Return the first documented example response's data points.

    Args:
        section: The endpoint's documentation section.

    Returns:
        list[dict[str, object]]: The data points of the first array-shaped
            example response.
    """
    examples = _data_point_examples(section)
    assert examples, "the documentation must show at least one example response body"
    return examples[0][1]


def _documented_schema_keys(section: str) -> set[str]:
    """Return the field names the documented response schema lists.

    Args:
        section: The endpoint's documentation section.

    Returns:
        set[str]: The keys of the object in the ``Response Schema`` block.
    """
    blocks = _labelled_blocks(section, "Response Schema")
    assert blocks, "the documentation must include a 'Response Schema' block"
    schema = json.loads(blocks[0][1])
    assert isinstance(schema, list), (
        "the response schema is a JSON array of data points"
    )
    assert len(schema) == 1, "the response schema describes one data point per entry"
    keys: set[str] = set(schema[0])
    return keys


def _status_code_entries(section: str) -> dict[str, str]:
    """Return the status codes listed in the section's status-code list.

    Only the ``**Status Codes**`` list counts: a code mentioned inside an
    example's label is not a documented status.

    Args:
        section: The endpoint's documentation section.

    Returns:
        dict[str, str]: ``{three-digit code: documented meaning}``.

    Raises:
        AssertionError: When the section has no status-code list.
    """
    lines = section.splitlines()
    starts = [
        index
        for index, line in enumerate(lines)
        if line.startswith("**Status Codes") and line.rstrip().endswith("**:")
    ]
    assert starts, "the section must list the status codes it can answer with"
    entries: dict[str, str] = {}
    for line in lines[starts[0] + 1 :]:
        if line.startswith("**"):
            break
        match = re.match(r"^- `(\d{3})[^`]*`: (\S.*)$", line)
        if match:
            entries[match.group(1)] = match.group(2)
    return entries


def _documented_allowed_methods(section: str) -> set[str]:
    """Return the methods the section says the path allows.

    Args:
        section: The endpoint's documentation section.

    Returns:
        set[str]: The method names taken from every ``Allow:`` mention.
    """
    mentions = re.findall(r"Allow:\s*([A-Z]+(?:\s*[,|/]\s*[A-Z]+)*)", section)
    return {
        token.strip()
        for mention in mentions
        for token in re.split(r"[,/|]", mention)
        if token.strip()
    }


def _deref(spec: dict[str, Any], node: Any) -> Any:
    """Resolve a local OpenAPI ``$ref`` against the document's components.

    Args:
        spec: The whole OpenAPI document.
        node: A schema node, possibly a ``$ref``.

    Returns:
        Any: The node with any local reference replaced by what it points at.
    """
    if isinstance(node, dict) and isinstance(node.get("$ref"), str):
        target: Any = spec
        for part in node["$ref"].lstrip("#/").split("/"):
            target = target[part]
        return _deref(spec, target)
    return node


def _operation() -> dict[str, Any]:
    """Return the published OpenAPI operation for this endpoint.

    Returns:
        dict[str, Any]: The ``get`` operation of the documented path.
    """
    spec = app.openapi()
    paths: dict[str, Any] = spec["paths"]
    assert ENDPOINT in paths, f"{ENDPOINT} must appear in the OpenAPI document"
    operation: dict[str, Any] = paths[ENDPOINT]["get"]
    return operation


def _operation_success_schema_keys() -> set[str]:
    """Return the fields the OpenAPI schema publishes for a data point.

    Returns:
        set[str]: The property names of the resolved ``200`` item schema.
    """
    spec = app.openapi()
    schema = _deref(
        spec, _operation()["responses"]["200"]["content"]["application/json"]
    )
    items = _deref(spec, schema["schema"]["items"])
    properties: dict[str, Any] = items["properties"]
    return set(properties)


async def _live_points(
    async_client: AsyncClient,
) -> list[dict[str, object]]:
    """Return the data points the running endpoint answers with.

    Args:
        async_client: The ASGI-transport client.

    Returns:
        list[dict[str, object]]: The decoded array of data points.
    """
    response = await async_client.get(ENDPOINT)
    assert response.status_code == HTTPStatus.OK, response.text
    body: list[dict[str, object]] = response.json()
    return body


class TestEndpointIsDocumented:
    """AC-001: the documentation includes GET /users/created-per-day."""

    def test_section_names_the_path_and_the_get_method(self) -> None:
        """AC-001: the endpoint's path and method are stated in its section."""
        section = _endpoint_section()

        assert ENDPOINT in section, "the endpoint path must be documented"
        assert f"GET {ENDPOINT}" in section, (
            "the documentation must name GET on this path"
        )
        assert f"#### GET {ENDPOINT}" in section, (
            "the section must head the endpoint with its method and path, as "
            "every other section in docs/API.md does"
        )

    def test_documented_path_and_method_are_the_routed_operation(self) -> None:
        """AC-001: what is documented is what the application routes."""
        section = _endpoint_section()
        documented_paths = re.findall(
            r"#### (GET|POST|PUT|PATCH|DELETE) (\S+)", section
        )

        assert documented_paths == [("GET", ENDPOINT)], (
            "this section must document exactly one operation: GET on the "
            f"documented path, got {documented_paths}"
        )
        assert ENDPOINT in app.openapi()["paths"], (
            f"the documented path must be routed, got {sorted(app.openapi()['paths'])}"
        )
        assert "get" in app.openapi()["paths"][ENDPOINT], (
            "the documented path must answer GET"
        )

    def test_other_methods_are_documented_as_refused(self) -> None:
        """AC-001: the document says GET is the only method this path serves."""
        section = _endpoint_section()

        assert "405" in section, (
            "the documentation must state that other methods are refused with 405"
        )
        assert _documented_allowed_methods(section) == {"GET"}, (
            "the documentation must promise GET as the only allowed method"
        )
        operations = set(app.openapi()["paths"][ENDPOINT])
        assert operations == {"get"}, (
            "the published contract lists GET only; if another method is "
            f"routed, the documentation must say so, got {sorted(operations)}"
        )

    def test_status_codes_are_documented(self) -> None:
        """AC-001: every status the operation publishes is listed, and explained."""
        section = _endpoint_section()
        entries = _status_code_entries(section)

        assert set(entries) == set(_operation()["responses"]), (
            "the documented status codes must be exactly the ones the operation "
            "publishes in its OpenAPI contract"
        )
        assert all(len(meaning) > 20 for meaning in entries.values()), (
            "each status code needs a sentence saying when it is returned"
        )


class TestResponseSchemaIsDocumented:
    """AC-002: the response schema is documented."""

    def test_schema_block_lists_the_model_fields(self) -> None:
        """AC-002: the schema block agrees with DailyCountResponse, field for field."""
        section = _endpoint_section()

        assert _documented_schema_keys(section) == set(
            DailyCountResponse.model_fields
        ), (
            "the documented response schema must list exactly the fields the "
            "response model declares"
        )

    def test_schema_block_agrees_with_the_openapi_component(self) -> None:
        """AC-002: the prose schema and the machine-readable schema agree."""
        section = _endpoint_section()

        assert _documented_schema_keys(section) == _operation_success_schema_keys(), (
            "the documented schema must carry the same fields as the OpenAPI "
            "schema published for this operation"
        )

    def test_every_schema_field_is_described(self) -> None:
        """AC-002: each field in the schema is described, not merely named."""
        section = _endpoint_section()
        entries = re.findall(
            r"^- `([^`]+)` \(([^)]+)\): (\S.*)$", section, re.MULTILINE
        )
        described = {name: (kind, text) for name, kind, text in entries}

        missing = set(DailyCountResponse.model_fields) - set(described)
        assert not missing, (
            "fields named in the response schema but never described in prose: "
            f"{sorted(missing)}"
        )
        assert all(kind.strip() for kind, _ in described.values()), (
            "each described field must state its type"
        )
        assert all(len(text) > 20 for _, text in described.values()), (
            "each described field needs a sentence of its own, not a bare word"
        )

    def test_documented_examples_satisfy_the_response_model(self) -> None:
        """AC-002: every documented data point is valid against the model."""
        section = _endpoint_section()
        examples = _data_point_examples(section)

        assert examples, "the documentation must show example response bodies"
        for label, points in examples:
            for point in points:
                DailyCountResponse.model_validate(point)  # raises on a bad example
                assert set(point) == set(DailyCountResponse.model_fields), (
                    f"{label} carries fields the response model does not declare"
                )


class TestExampleRequestAndResponse:
    """AC-003: an example request and response are included."""

    def test_example_request_is_an_invocable_get(self) -> None:
        """AC-003: the example request can be run against the documented path."""
        section = _endpoint_section()
        requests = _labelled_blocks(section, "Example Request")

        assert requests, "the documentation must include an example request"
        get_requests = [
            body for label, body in requests if "Unsupported Method" not in label
        ]
        assert get_requests, "a GET example request must be shown"
        assert all("curl" in body for body in get_requests), (
            "the example request must be a curl invocation"
        )
        assert any(ENDPOINT in body and "-X GET" in body for body in get_requests), (
            "the example request must issue GET against the documented path"
        )

    def test_example_response_is_the_documented_window_oldest_first(self) -> None:
        """AC-003: the example shows consecutive days, oldest first, with counts."""
        points = _example_points(_endpoint_section())

        assert len(points) == WINDOW_DAYS, (
            "the example must show the same number of data points as the "
            "endpoint returns"
        )
        days = [date.fromisoformat(str(point["date"])) for point in points]
        assert days == sorted(days), "the example must be ordered oldest day first"
        steps = [later - earlier for earlier, later in zip(days, days[1:])]
        assert all(step == timedelta(days=1) for step in steps), (
            f"the example days must be consecutive, got {days}"
        )
        assert all(isinstance(point["count"], int) for point in points), (
            "every example count must be an integer"
        )

    async def test_example_response_shape_matches_the_live_response(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-003: what the document shows is what the endpoint sends."""
        live = await _live_points(async_client)
        examples = _data_point_examples(_endpoint_section())

        assert examples, "the documentation must show an example response body"
        for label, points in examples:
            assert len(points) == len(live), (
                f"{label} shows {len(points)} data points; the endpoint answers "
                f"with {len(live)}"
            )
            assert [set(point) for point in points] == [set(point) for point in live], (
                f"{label} does not carry the same fields as a live response"
            )
            assert [type(point["count"]) for point in points] == [
                type(point["count"]) for point in live
            ], f"{label} does not type 'count' as the endpoint does"

    async def test_documented_405_example_matches_the_live_refusal(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-003: the documented 405 body and Allow header are the real ones."""
        section = _endpoint_section()
        documented = _error_example(section, "405")

        response = await async_client.post(ENDPOINT)

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
        assert response.json() == documented, (
            "the documented 405 body must be the body the endpoint answers with"
        )
        live_allowed = {
            token.strip()
            for token in response.headers["allow"].split(",")
            if token.strip()
        }
        assert live_allowed == _documented_allowed_methods(section), (
            "the Allow header the endpoint sends must name the methods the "
            "documentation names"
        )

    async def test_documented_503_example_matches_the_error_contract(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-003: the documented 503 body is the one this service raises."""
        documented = _error_example(_endpoint_section(), "503")

        assert documented == error_body(DatabaseUnavailableError.default_detail), (
            "the documented 503 body must be the body the shared error handler "
            "produces, word for word"
        )

        failure = OperationalError(DRIVER_MESSAGE, {}, ConnectionRefusedError())
        with patch.object(
            crud, "count_users_created_per_day", AsyncMock(side_effect=failure)
        ):
            response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert response.json() == documented, (
            "a database failure must answer with the documented 503 body"
        )


class TestModifiedFilesPassConfiguredChecks:
    """AC-004: the files this task touched pass the project's own checks."""

    def test_documented_section_follows_the_documents_markdown_conventions(
        self,
    ) -> None:
        """AC-004: the edited section is formatted like the rest of docs/API.md."""
        section = _endpoint_section()
        lines = section.splitlines()

        assert lines[0] == SECTION_HEADING, (
            "the section must open with its level-3 heading, as every endpoint "
            "section in docs/API.md does"
        )
        assert any(line.startswith("#### ") for line in lines), (
            "the section must carry the level-4 method-and-path heading"
        )
        assert not [line for line in lines if line != line.rstrip()], (
            "no line in the section may end with trailing whitespace"
        )
        assert not [line for line in lines if line.startswith("\t")], (
            "the section must be indented with spaces, as the rest of the file"
        )
        fences = re.findall(r"^[ \t]*```([A-Za-z]*)", section, re.MULTILINE)
        assert len(fences) % 2 == 0, "every code fence in the section must be closed"
        assert all(tag for tag in fences[::2]), (
            "every opened code fence must name its language, as elsewhere in "
            "docs/API.md"
        )

    def test_python_files_touched_by_this_task_pass_ruff(self) -> None:
        """AC-004: ruff, the linter and formatter pyproject configures, is clean."""
        ruff = subprocess.run(
            [sys.executable, "-m", "ruff", "--version"],
            capture_output=True,
            check=False,
        )
        if ruff.returncode != 0:
            pytest.skip("ruff is not installed in this environment")

        targets = [str(Path(__file__))]
        for arguments in (["check"], ["format", "--check"]):
            result = subprocess.run(
                [sys.executable, "-m", "ruff", *arguments, *targets],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, (
                f"`ruff {' '.join(arguments)}` reported errors on {targets}:\n"
                f"{result.stdout}{result.stderr}"
            )
