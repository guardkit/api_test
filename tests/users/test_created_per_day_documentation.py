"""Documentation tests for the GET /users/created-per-day analytics endpoint.

Covers TASK-BD8F-005 (update the API documentation):

- AC-001: ``docs/API.md`` describes the endpoint — its method and path, its
  authentication, the fields of its response, and the status codes it answers with.
- AC-002: it shows an example request and example responses, and those examples are
  the real thing: the documented request authenticates, and every documented success
  example is a body the application's own response model accepts.

Why the tests read the application rather than a list written here. Documentation is
only worth having if it agrees with the code, so what it has to agree with is taken
from the code at test time: the route the handler is mounted on, the response schema
the OpenAPI document publishes, the token the router accepts, and the answers a live
request actually gets. A documented field the application does not answer with, or an
example token the application would reject, fails these tests. The prose itself is
free; the contract it describes is not.

Nothing here pins a task boundary. The endpoint, its router and its CRUD layer were
shipped by earlier tasks of FEAT-BD8F (TASK-BD8F-002 through TASK-BD8F-004) and are
exercised by their own suites (``tests/users/test_created_per_day_endpoint.py``,
``tests/users/test_users_created_per_day.py``, ``tests/test_analytics_models.py``);
this file asks only whether the documentation keeps pace with them.
"""

from __future__ import annotations

import inspect
import json
import re
import subprocess
import sys
import types
from datetime import date, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any, NoReturn

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from src.db.dependencies import get_db as app_get_db
from src.main import app
from src.users import router as users_router
from src.users.calculations import recent_creation_window_end
from src.users.models import User
from src.users.router import analytics_router, get_users_created_per_day
from src.users.schemas import DEFAULT_USER_CREATION_WINDOW_DAYS, UserCreationStats

# tests/users/<this file> -> the repository root, where docs/ lives.
API_DOCS_PATH = Path(__file__).resolve().parents[2] / "docs" / "API.md"

# The Python files this task touches. Documentation is prose and cannot be linted;
# the one Python file it comes with can, and the project's own toolchain is what
# decides — see ``test_the_configured_lint_and_format_pass_on_this_task_s_files``.
THIS_TASKS_PYTHON_FILES: tuple[Path, ...] = (Path(__file__).resolve(),)

# Methods that write, and so are answered on this path by something other than the
# analytics handler. A documentation claim is only worth testing if it covers every
# way a caller can reach the path, not just the one the Gherkin happens to name.
WRITE_METHODS: tuple[str, ...] = ("POST", "PUT", "PATCH", "DELETE")

# Heads each shown example response, e.g.
# **Example Response (Happy Path — seven days, oldest first)**:
_EXAMPLE_MARKER = r"\*\*Example Response \(([^)]*)\)\*\*:?\s*```json\n(.*?)```"


class _RefusingSession:
    """A database session that fails the way an unreachable database fails.

    Used to put the endpoint in the failure state its documentation describes, so the
    shown 503 body can be compared with the one the application really answers.
    """

    async def execute(self, *_args: object, **_kwargs: object) -> NoReturn:
        """Refuse every statement, as a refused connection does.

        Raises:
            SQLAlchemyError: Always, with the message a refused connection gives.
        """
        raise SQLAlchemyError("connection to server at localhost port 5432 failed")


def refusing_session() -> object:
    """Return the session the endpoint cannot get an answer out of.

    Returns:
        object: A session that raises on every statement it is handed.
    """
    return _RefusingSession()


# Heads each shown example response, e.g.
# **Example Response (Happy Path — seven days, oldest first)**:
_EXAMPLE_MARKER = r"\*\*Example Response \(([^)]*)\)\*\*:?\s*```json\n(.*?)```"


def docs_text() -> str:
    """Return the API documentation as one string.

    Returns:
        str: The full text of ``docs/API.md``.

    Raises:
        AssertionError: If the documentation file is not there to be read.
    """
    assert API_DOCS_PATH.is_file(), f"{API_DOCS_PATH} must exist to be documented in"
    return API_DOCS_PATH.read_text(encoding="utf-8")


def served_endpoint() -> tuple[str, str]:
    """Return the method and path the handler is declared on.

    The declaration, not a copy: the router's own route table, so a path or verb
    that moved in the code moves the documentation's target here too. That the
    application really serves that pair is proved by a live request in
    ``test_the_documented_path_is_served_by_the_application``.

    Returns:
        tuple[str, str]: The one HTTP method and path the handler answers on.

    Raises:
        AssertionError: If the handler is declared other than exactly once.
    """
    mounted = [
        (sorted(route.methods or ())[0], route.path)
        for route in analytics_router.routes
        if isinstance(route, APIRoute) and route.endpoint is get_users_created_per_day
    ]
    assert len(mounted) == 1, f"handler declared oddly: {mounted}"
    return mounted[0]


def endpoint_section(text: str) -> str:
    """Return the part of the documentation that describes the analytics endpoint.

    Args:
        text: The full text of ``docs/API.md``.

    Returns:
        str: The endpoint's section, from its ``#### METHOD /path`` heading to the
        next heading of any level.

    Raises:
        AssertionError: If no heading names the method and path the application
            actually serves, which is the documentation having drifted from the route.
    """
    method, path = served_endpoint()
    heading = f"#### {method} {path}"
    start = text.find(heading)
    assert start != -1, f"docs/API.md must head the endpoint as {heading}"
    rest = text[start + len(heading) :]
    following = re.search(r"^(?:#{1,4} )", rest, flags=re.M)
    end = start + len(heading) + (following.start() if following else 0)
    return text[start:end]


def fenced_blocks(section: str, language: str) -> list[str]:
    """Return the body of every fenced block of one language in a section.

    Args:
        section: The documented section to read.
        language: The fence language to keep, e.g. ``json`` or ``bash``.

    Returns:
        list[str]: The block bodies, in the order they appear.
    """
    pattern = rf"```{language}\n(.*?)```"
    return [block.strip() for block in re.findall(pattern, section, flags=re.S)]


def documented_examples(section: str) -> list[tuple[str, Any]]:
    """Return the labelled example responses the section shows.

    Args:
        section: The documented section to read.

    Returns:
        list[tuple[str, Any]]: One ``(label, decoded body)`` pair for each
        ``**Example Response (label)**`` marker, in the order they appear.

    Raises:
        json.JSONDecodeError: If a shown example is not valid JSON.
    """
    pairs: list[tuple[str, Any]] = []
    for match in re.finditer(_EXAMPLE_MARKER, section, flags=re.S):
        pairs.append((match.group(1).strip(), json.loads(match.group(2))))
    return pairs


def documented_response_schema(section: str) -> dict[str, Any]:
    """Return the JSON block the section shows as its response schema.

    Args:
        section: The documented section to read.

    Returns:
        dict[str, Any]: The shown schema example, decoded.

    Raises:
        AssertionError: If the section shows no JSON block to read as a schema.
    """
    blocks = fenced_blocks(section, "json")
    assert blocks, "the endpoint section must show a response schema"
    decoded = json.loads(blocks[0])
    assert isinstance(decoded, dict), "the response schema must be a JSON object"
    return decoded


def success_examples(section: str) -> list[tuple[str, dict[str, Any]]]:
    """Return the example responses that carry a per-day window.

    Args:
        section: The documented section to read.

    Returns:
        list[tuple[str, dict[str, Any]]]: The ``(label, body)`` pairs of the
        successful examples, which are the ones showing ``days``.
    """
    successes: list[tuple[str, dict[str, Any]]] = []
    for label, body in documented_examples(section):
        if isinstance(body, dict) and "days" in body:
            successes.append((label, body))
    return successes


def documented_request_headers(section: str) -> dict[str, str]:
    """Return the request headers the documented curl example sends.

    Args:
        section: The documented section to read.

    Returns:
        dict[str, str]: Header names to values, as the example writes them.
    """
    headers: dict[str, str] = {}
    for block in fenced_blocks(section, "bash"):
        for name, value in re.findall(r'-H\s+"([^":]+):\s*([^"]+)"', block):
            headers[name.strip()] = value.strip()
    return headers


def published_response_schema() -> dict[str, Any]:
    """Return the OpenAPI component the endpoint answers with.

    Returns:
        dict[str, Any]: The schema component the 200 response references.

    Raises:
        AssertionError: If the endpoint publishes no JSON schema for a 200 answer.
    """
    schema: dict[str, Any] = app.openapi()
    method, path = served_endpoint()
    responses = schema["paths"][path][method.lower()]["responses"]
    two_hundred = responses.get("200")
    assert isinstance(two_hundred, dict), "the endpoint must declare a 200 response"
    schema_node = two_hundred["content"]["application/json"]["schema"]
    assert isinstance(schema_node, dict)
    return resolve_schema(schema_node)


def resolve_schema(node: dict[str, Any]) -> dict[str, Any]:
    """Return the schema a node points at, following a ``$ref`` if it carries one.

    Args:
        node: A schema node from the OpenAPI document.

    Returns:
        dict[str, Any]: The node itself, or the component it references.

    Raises:
        AssertionError: If a reference names a component the document lacks.
    """
    reference = node.get("$ref")
    if reference is None:
        return node
    walked: Any = app.openapi()
    for part in str(reference).lstrip("#/").split("/"):
        walked = walked[part]
    assert isinstance(walked, dict), f"{reference} does not name a schema"
    return walked


def published_status_codes() -> list[str]:
    """Return the status codes the application declares for the endpoint.

    Returns:
        list[str]: The codes the framework publishes, sorted, e.g. ``200``.
    """
    schema: dict[str, Any] = app.openapi()
    method, path = served_endpoint()
    operations = schema["paths"][path][method.lower()]["responses"]
    return sorted(operations)


def status_codes_block(section: str) -> str:
    """Return the list of status codes the section carries.

    Args:
        section: The documented section to read.

    Returns:
        str: The text under the ``**Status Codes**`` marker.

    Raises:
        AssertionError: If the section lists no status codes.
    """
    match = re.search(
        r"\*\*Status Codes\*\*:?\s*\n(.*?)(?:\n\s*\n\*\*|\n---|\Z)", section, flags=re.S
    )
    assert match is not None, "the endpoint section must list its status codes"
    return match.group(1)


def window_of(example: dict[str, Any]) -> list[date]:
    """Return the days one shown example carries, in the order it carries them.

    Args:
        example: One decoded successful example body.

    Returns:
        list[date]: The days of the example, oldest first as written.
    """
    days = example["days"]
    assert isinstance(days, list)
    return [date.fromisoformat(str(entry["date"])) for entry in days]


class TestEndpointIsDocumented:
    """AC-001: ``docs/API.md`` describes the endpoint."""

    def test_the_documentation_file_is_where_it_is_written_to_be(self) -> None:
        """AC-001: the file this task updates exists."""
        assert API_DOCS_PATH.is_file()

    def test_the_endpoint_is_headed_by_the_route_it_is_served_on(self) -> None:
        """AC-001: the heading names the method and path the application serves."""
        method, path = served_endpoint()

        assert f"#### {method} {path}" in docs_text()

    async def test_the_documented_path_is_served_by_the_application(
        self,
        async_client: AsyncClient,
    ) -> None:
        """AC-001: the documented route is one the application really answers."""
        method, path = served_endpoint()
        operations: dict[str, Any] = app.openapi()["paths"]

        assert path in operations, f"{path} is published by no route the app exports"
        assert method.lower() in operations[path], f"{method} {path} is not published"

        answered = await async_client.request(method, path)
        assert answered.status_code != HTTPStatus.NOT_FOUND, f"{path} answers 404"
        assert answered.status_code == HTTPStatus.FORBIDDEN, (
            "the analytics handler is not what answers the documented path: "
            f"{answered.status_code} {answered.text}"
        )

    def test_the_section_describes_the_endpoint_in_prose(self) -> None:
        """AC-001: the section says in words what the endpoint answers."""
        section = endpoint_section(docs_text())

        assert len(section.splitlines()) > 20, (
            "the section is a stub, not a description"
        )
        assert "created on each" in section.lower()

    def test_every_documented_endpoint_heading_is_a_route_the_app_serves(self) -> None:
        """AC-001: no heading in the documentation names a route that is not served."""
        headings = re.findall(r"^####\s+([A-Z]+)\s+(\S+)\s*$", docs_text(), flags=re.M)
        assert headings, "the documentation documents no endpoints at all"
        operations: dict[str, Any] = app.openapi()["paths"]

        for method, path in headings:
            assert path in operations, f"documented path {path} is not served"
            assert method.lower() in operations[path], f"{method} {path} is not served"

    async def test_the_documented_authentication_header_is_the_one_the_app_enforces(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """AC-001: the header the section names is the header that gets you in."""
        section = endpoint_section(docs_text())
        headers = documented_request_headers(section)
        _, path = served_endpoint()

        assert headers, "the example request must show the headers it sends"
        assert "authentication" in section.lower()

        without = await async_client.get(path)
        assert without.status_code == HTTPStatus.FORBIDDEN

        documented = await async_client.get(path, headers=headers)
        assert documented.status_code == HTTPStatus.OK, (
            f"the documented headers {sorted(headers)} do not authenticate: "
            f"{documented.status_code} {documented.text}"
        )

    def test_the_section_lists_every_status_code_the_app_declares(self) -> None:
        """AC-001: every code the endpoint declares for itself is listed."""
        listed = status_codes_block(endpoint_section(docs_text()))

        for code in published_status_codes():
            assert code in listed, f"status code {code} is not in the documented list"

    def test_the_section_answers_for_the_window_the_endpoint_uses(self) -> None:
        """AC-001: the window the prose describes is the window the code answers."""
        section = endpoint_section(docs_text())

        assert str(DEFAULT_USER_CREATION_WINDOW_DAYS) in section, (
            "the section must state how many days the window spans"
        )
        assert "yesterday" in section.lower(), (
            "the window ends the day before today; the section has to say so"
        )

    def test_the_documented_token_is_the_token_the_router_accepts(self) -> None:
        """AC-001: the example carries the token the router checks, not a stale one."""
        headers = documented_request_headers(endpoint_section(docs_text()))

        assert headers, "the example request must show the headers it sends"
        assert users_router.AUTH_TOKEN in " ".join(headers.values()), (
            "the documented token is not the one the router accepts"
        )

    def test_the_timestamp_the_section_groups_by_is_the_naive_one_it_claims(
        self,
    ) -> None:
        """AC-001: the column the section names really is the one it describes.

        The section says the days are grouped from ``created_at``, which the model
        stores as naive UTC, and draws a conclusion from that — SQLite and PostgreSQL
        group the same way. The conclusion holds only while the column carries no
        timezone, so the column is read from the model rather than taken on trust from
        the prose.
        """
        section = endpoint_section(docs_text())
        column = User.__table__.c["created_at"]

        assert "created_at" in section, (
            "the section must name the column the days are grouped from"
        )
        assert "naive" in section.lower(), (
            "the section must say what kind of timestamp it groups by, because that "
            "is what makes the answer the same on either database"
        )
        assert not getattr(column.type, "timezone", False), (
            f"created_at is {column.type}: the section's claim that either database "
            "groups alike depends on that column carrying no timezone"
        )


class TestExamplesAgreeWithTheApplication:
    """AC-002: the example request and responses are the real thing."""

    def test_an_example_request_is_shown_as_a_curl_call_to_the_served_path(
        self,
    ) -> None:
        """AC-002: a request a person can paste is shown, at the served path."""
        _, path = served_endpoint()
        blocks = fenced_blocks(endpoint_section(docs_text()), "bash")

        assert blocks, "the section must show at least one example request"
        assert any("curl" in block for block in blocks)
        assert any(path in block for block in blocks)

    def test_the_field_names_shown_are_the_names_the_app_publishes(self) -> None:
        """AC-002: the schema block and the OpenAPI component name the same fields."""
        section = endpoint_section(docs_text())
        shown = documented_response_schema(section)
        published = published_response_schema()
        published_fields = set(published["properties"])

        assert set(shown) == published_fields, (
            "the documented fields are not the fields the endpoint answers with"
        )

        item_fields = set(
            resolve_schema(published["properties"]["days"]["items"])["properties"]
        )
        shown_days = shown["days"]
        assert isinstance(shown_days, list) and shown_days
        assert set(shown_days[0]) == item_fields

        for field in published_fields | item_fields:
            assert field in section, f"field {field} is shown but never described"

    def test_every_success_example_is_a_body_the_response_model_accepts(self) -> None:
        """AC-002: each shown success example validates as a real response."""
        examples = success_examples(endpoint_section(docs_text()))

        assert examples, "the section must show at least one successful response"
        for label, body in examples:
            parsed = UserCreationStats.model_validate(body)
            assert parsed.total == body["total"], label
            shown_counts = [entry["count"] for entry in body["days"]]
            assert [day.count for day in parsed.days] == shown_counts, label

    def test_the_success_examples_show_the_window_the_endpoint_answers(self) -> None:
        """AC-002: examples show one unbroken run of days, oldest first, summed."""
        examples = success_examples(endpoint_section(docs_text()))

        assert examples, "the section must show at least one successful response"
        for label, body in examples:
            days = window_of(body)
            assert len(days) == DEFAULT_USER_CREATION_WINDOW_DAYS, label
            assert days == sorted(days), f"{label}: days are not oldest first"
            steps = [later - earlier for earlier, later in zip(days, days[1:])]
            assert all(step == timedelta(days=1) for step in steps), (
                f"{label}: the days are not one unbroken run"
            )
            counts = body["days"]
            assert body["total"] == sum(int(entry["count"]) for entry in counts), label

    async def test_the_error_examples_match_the_errors_the_application_gives(
        self,
        async_client: AsyncClient,
    ) -> None:
        """AC-002: the shown 403 body is what an unauthenticated call gets."""
        _, path = served_endpoint()
        bodies = [
            body
            for label, body in documented_examples(endpoint_section(docs_text()))
            if label.startswith("403") and isinstance(body, dict)
        ]

        assert bodies, "the section must show what an unauthorized request gets back"
        live = await async_client.get(path)
        assert live.status_code == HTTPStatus.FORBIDDEN
        assert live.json() in bodies, f"live 403 {live.json()} is not the shown body"


class TestLiveResponsesMatchTheDocumentation:
    """The documentation describes the answers the endpoint really gives."""

    async def test_the_live_body_carries_exactly_the_documented_fields(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """A real answer is made of the fields the documentation lists."""
        section = endpoint_section(docs_text())
        headers = documented_request_headers(section)
        shown = documented_response_schema(section)
        _, path = served_endpoint()

        response = await async_client.get(path, headers=headers)
        assert response.status_code == HTTPStatus.OK

        body: Any = response.json()
        assert isinstance(body, dict)
        assert set(body) == set(shown), "the live body left the documented fields"

        days = body["days"]
        assert isinstance(days, list) and days
        for entry in days:
            assert isinstance(entry, dict)
            assert set(entry) == set(shown["days"][0]), "a live day left the schema"

    async def test_the_live_window_ends_the_day_the_documentation_says(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """The newest day of a real answer is the day before today, as documented."""
        section = endpoint_section(docs_text())
        headers = documented_request_headers(section)
        _, path = served_endpoint()

        response = await async_client.get(path, headers=headers)
        assert response.status_code == HTTPStatus.OK

        days = response.json()["days"]
        assert isinstance(days, list) and days
        assert date.fromisoformat(str(days[-1]["date"])) == recent_creation_window_end()
        assert "yesterday" in section.lower()

    async def test_an_unauthenticated_request_is_refused_in_the_documented_words(
        self,
        async_client: AsyncClient,
    ) -> None:
        """The refusal a tokenless request is told appears in the documentation."""
        section = endpoint_section(docs_text())
        _, path = served_endpoint()

        response = await async_client.get(path)
        assert response.status_code == HTTPStatus.FORBIDDEN
        detail = str(response.json()["detail"])
        assert detail in section, f"the section omits the refusal: {detail}"

    async def test_every_write_method_refusal_is_documented_in_the_words_it_gives(
        self,
        async_client: AsyncClient,
    ) -> None:
        """AC-001: what each write method is answered with on this path is written down.

        Only GET is registered on the analytics path, so a write method lands either on
        the router's method refusal or on the `/users/{user_id}` routes this path is
        registered ahead of. Which of the two it is comes from the application's route
        table at test time, so a claim that names one code for every method fails the
        moment the application answers the others differently.
        """
        section = endpoint_section(docs_text())
        listed = status_codes_block(section)
        _, path = served_endpoint()

        for method in WRITE_METHODS:
            refused = await async_client.request(method, path)
            assert refused.status_code != HTTPStatus.OK, f"{method} {path} answered 200"

            code = str(refused.status_code)
            assert code in listed, (
                f"{method} {path} answers {code}, which the section does not list"
            )
            detail = str(refused.json().get("detail", ""))
            assert detail, f"{method} {path} refused without saying why"
            assert detail in section, (
                f"{method} {path} is told {detail!r}, which the section omits"
            )

    async def test_the_documented_etag_promise_holds_on_this_path(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """AC-001: the ETag the section says this path inherits really comes with it."""
        section = endpoint_section(docs_text())
        headers = documented_request_headers(section)
        _, path = served_endpoint()

        assert "ETag" in section, (
            "the section no longer says what conditional requests do on this path"
        )

        answered = await async_client.get(path, headers=headers)
        assert answered.status_code == HTTPStatus.OK
        assert "ETag" in answered.headers, (
            "the section promises an ETag on this path; the answer carries none"
        )

        conditional = await async_client.get(
            path,
            headers={**headers, "If-None-Match": answered.headers["ETag"]},
        )
        assert conditional.status_code == HTTPStatus.NOT_MODIFIED, (
            "the section points at If-None-Match handling that this path does not do: "
            f"{conditional.status_code}"
        )

    async def test_a_refused_count_answers_the_documented_503_shape(
        self,
        async_client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-002: the shown 503 body is the shape a refused count really answers.

        The database is put where the documentation's worst case puts it — reachable
        in name, refusing in fact — and the answer is read back. The prefix the shown
        detail opens with is taken from the documentation, so it is the document that
        makes the promise and the application that has to keep it.
        """
        section = endpoint_section(docs_text())
        _, path = served_endpoint()
        shown = [
            body
            for label, body in documented_examples(section)
            if label.startswith("503") and isinstance(body, dict)
        ]

        assert shown, "the section must show what a refused count answers with"
        shown_detail = str(shown[0].get("detail", ""))
        assert shown_detail, "the shown 503 body must say why the count failed"
        colon = shown_detail.find(":")
        prefix = shown_detail[: colon + 1] if colon != -1 else shown_detail

        monkeypatch.setitem(app.dependency_overrides, app_get_db, refusing_session)
        refused = await async_client.get(
            path, headers=documented_request_headers(section)
        )

        assert refused.status_code == HTTPStatus.SERVICE_UNAVAILABLE, (
            f"a refused count answered {refused.status_code}, not 503: {refused.text}"
        )
        live_detail = str(refused.json()["detail"])
        assert live_detail.startswith(prefix), (
            f"the live detail {live_detail!r} does not open with the documented "
            f"{prefix!r}"
        )


class TestTheTaskPassesTheConfiguredChecks:
    """AC-003/AC-004: the checks the project configures, run on this task's files."""

    def test_the_configured_lint_and_format_pass_on_this_task_s_files(self) -> None:
        """AC-003: the project's own linter and formatter, over the files it changed.

        The check is the one the repository declares (`[tool.ruff]` in pyproject), run
        from the repository root so it reads that configuration; nothing here repeats
        a rule list that would silently disagree with it. The whole repository is
        deliberately not swept — this criterion is about the files this task touched,
        and the rest of the tree carries findings that belong to other tasks.

        Raises:
            AssertionError: If the configured check reports anything on a file this
                task touched.
        """
        root = API_DOCS_PATH.parent.parent
        ruff = Path(sys.executable).with_name("ruff")
        if not ruff.is_file():
            pytest.skip(
                "ruff is not installed in this interpreter, so the project-configured "
                "check cannot be run here; it is declared in pyproject extras [dev]"
            )

        for target in THIS_TASKS_PYTHON_FILES:
            relative = target.relative_to(root)
            for arguments in (["check", "--quiet"], ["format", "--check"]):
                finished = subprocess.run(  # noqa: S603
                    [str(ruff), *arguments, str(relative)],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                assert finished.returncode == 0, (
                    f"ruff {' '.join(arguments)} reported {relative}:\n"
                    f"{finished.stdout}{finished.stderr}"
                )

    def test_the_documentation_file_is_well_formed_markdown(self) -> None:
        """AC-003: the prose file this task changed holds together structurally.

        The configured toolchain lints Python and has nothing to say about markdown,
        so what can be checked about the documentation is checked here rather than
        waved through: every fence it opens it closes, and every JSON block it shows
        is JSON. A half-written block is a documentation defect no linter would catch.

        Raises:
            AssertionError: If a fence is left open or a JSON block does not parse.
        """
        text = docs_text()
        fences = re.findall(r"^\s*```", text, flags=re.M)
        assert len(fences) % 2 == 0, (
            f"{API_DOCS_PATH.name} opens {len(fences)} fences — an odd number leaves "
            "one unclosed, and everything after it renders as code"
        )

        json_blocks = re.findall(r"```json\n(.*?)```", text, flags=re.S)
        for number, block in enumerate(json_blocks, start=1):
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                raise AssertionError(
                    f"json block #{number} in {API_DOCS_PATH.name} is not JSON: {exc}"
                ) from exc


def test_every_function_in_this_file_declares_its_annotations() -> None:
    """AC-004: every argument and every return in this file carries a type."""
    module = inspect.getmodule(
        test_every_function_in_this_file_declares_its_annotations
    )
    assert module is not None

    members: list[object] = list(vars(module).values())
    for member in list(vars(module).values()):
        if isinstance(member, type) and member.__module__ == module.__name__:
            members.extend(vars(member).values())

    functions = [
        attribute
        for attribute in members
        if isinstance(attribute, types.FunctionType)
        and attribute.__module__ == module.__name__
    ]
    assert functions, "this file defines no functions to check"

    for function in functions:
        signature = inspect.signature(function)
        assert signature.return_annotation is not inspect.Parameter.empty, (
            f"{function.__name__} has no return annotation"
        )
        for name, parameter in signature.parameters.items():
            if name in {"self", "cls"}:
                continue
            assert parameter.annotation is not inspect.Parameter.empty, (
                f"{function.__name__}({name}) has no annotation"
            )
