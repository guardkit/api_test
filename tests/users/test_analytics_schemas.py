"""Tests for the user creation analytics response schemas.

These pin the response shape declared in src/users/analytics_schemas.py: a JSON
array of ``{"date": <ISO-8601>, "count": <int>}`` objects. They are pure-shape
checks — no database, no route. The 7-day window, the ordering and the
inclusion of soft-deleted users are the query's contract and belong to
TASK-E592-002 (src/users/analytics_crud.py) and TASK-E592-003
(src/users/analytics_router.py), whose tests live in tests/users/test_analytics.py
(TASK-E592-004).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

import pytest
from pydantic import BaseModel, RootModel, ValidationError

import src.users
from src.users.analytics_schemas import (
    UserCreatedPerDayEntry,
    UserCreatedPerDayResponse,
)

# A response body of the shape the endpoint must produce: oldest day first.
RESPONSE_BODY: list[dict[str, str | int]] = [
    {"date": "2026-09-27", "count": 0},
    {"date": "2026-09-28", "count": 4},
    {"date": "2026-09-29", "count": 1},
    {"date": "2026-09-30", "count": 0},
    {"date": "2026-10-01", "count": 9},
    {"date": "2026-10-02", "count": 2},
    {"date": "2026-10-03", "count": 7},
]


def _entry_schema() -> dict[str, Any]:
    """Return the JSON schema of a single day entry, resolving any $ref."""
    schema: dict[str, Any] = UserCreatedPerDayResponse.model_json_schema()
    definitions: dict[str, Any] = schema.get("$defs", {})
    items: dict[str, Any] = schema["items"]
    reference: str | None = items.get("$ref")
    if reference is not None:
        name: str = reference.rsplit("/", 1)[-1]
        items = definitions[name]
    return items


class TestUserCreatedPerDayEntry:
    """Tests for the per-day entry model."""

    def test_is_a_pydantic_model(self) -> None:
        """The entry is a Pydantic model, not a plain dataclass or TypedDict."""
        assert issubclass(UserCreatedPerDayEntry, BaseModel)

    def test_declares_exactly_a_date_and_a_count_key(self) -> None:
        """The entry's keys are the two the response contract names."""
        assert set(UserCreatedPerDayEntry.model_fields) == {"date", "count"}

    def test_validates_a_day_entry(self) -> None:
        """An ISO-8601 date and an integer count validate unchanged."""
        entry = UserCreatedPerDayEntry(date="2026-10-03", count=7)

        assert entry.date == "2026-10-03"
        assert entry.count == 7
        assert entry.model_dump() == {"date": "2026-10-03", "count": 7}

    def test_accepts_a_plain_mapping(self) -> None:
        """A dict of the response shape validates without keyword unpacking."""
        entry = UserCreatedPerDayEntry.model_validate(
            {"date": "2026-10-03", "count": 0}
        )

        assert entry.model_dump() == {"date": "2026-10-03", "count": 0}

    def test_json_schema_types_date_as_string_and_count_as_integer(self) -> None:
        """The advertised types are string for date, integer for count."""
        schema = UserCreatedPerDayEntry.model_json_schema()

        assert schema["properties"]["date"]["type"] == "string"
        assert schema["properties"]["count"]["type"] == "integer"
        assert set(schema["required"]) == {"date", "count"}

    @pytest.mark.parametrize("bad_count", ["three", None, 1.5, [1]])
    def test_rejects_a_count_that_is_not_an_integer(self, bad_count: Any) -> None:
        """A count that is not an integer is a validation error."""
        with pytest.raises(ValidationError):
            UserCreatedPerDayEntry.model_validate(
                {"date": "2026-10-03", "count": bad_count}
            )

    def test_rejects_a_missing_key(self) -> None:
        """Both keys are required."""
        with pytest.raises(ValidationError):
            UserCreatedPerDayEntry.model_validate({"date": "2026-10-03"})
        with pytest.raises(ValidationError):
            UserCreatedPerDayEntry.model_validate({"count": 3})

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (date(2026, 10, 3), "2026-10-03"),
            (datetime(2026, 10, 3, 8, 30, tzinfo=UTC), "2026-10-03"),
            ("2026-10-03", "2026-10-03"),
        ],
    )
    def test_normalizes_the_date_to_an_iso8601_string(
        self, value: date | datetime | str, expected: str
    ) -> None:
        """A date or datetime from the query layer lands as an ISO-8601 string."""
        entry = UserCreatedPerDayEntry.model_validate({"date": value, "count": 2})

        assert entry.date == expected
        assert isinstance(entry.date, str)


class TestUserCreatedPerDayResponse:
    """Tests for the response model of the whole body."""

    def test_is_a_pydantic_root_model_over_a_list(self) -> None:
        """The body is a list at the top level, so it is a RootModel."""
        assert issubclass(UserCreatedPerDayResponse, RootModel)
        assert issubclass(UserCreatedPerDayResponse, BaseModel)

    def test_validates_a_list_of_day_entries(self) -> None:
        """A list of date/count dicts validates and round-trips unchanged."""
        response = UserCreatedPerDayResponse.model_validate(RESPONSE_BODY)

        assert response.model_dump() == RESPONSE_BODY

    def test_serializes_as_a_list_of_plain_dictionaries(self) -> None:
        """The dumped body is list[dict[str, str | int]], as the contract says."""
        dumped = UserCreatedPerDayResponse.model_validate(RESPONSE_BODY).model_dump()

        assert isinstance(dumped, list)
        assert len(dumped) == len(RESPONSE_BODY)
        for entry in dumped:
            assert isinstance(entry, dict)
            assert set(entry) == {"date", "count"}
            assert isinstance(entry["date"], str)
            assert isinstance(entry["count"], int)

    def test_json_form_is_a_bare_array_of_objects(self) -> None:
        """The wire form is a JSON array, not an object wrapping one."""
        payload = json.loads(
            UserCreatedPerDayResponse.model_validate(RESPONSE_BODY).model_dump_json()
        )

        assert isinstance(payload, list)
        assert payload == RESPONSE_BODY

    def test_json_schema_is_an_array_of_day_entries(self) -> None:
        """The advertised body is an array whose items carry date and count."""
        schema = UserCreatedPerDayResponse.model_json_schema()

        assert schema["type"] == "array"
        items = _entry_schema()
        assert items["type"] == "object"
        assert set(items["properties"]) == {"date", "count"}
        assert items["properties"]["date"]["type"] == "string"
        assert items["properties"]["count"]["type"] == "integer"

    @pytest.mark.parametrize(
        "bad_body",
        [
            {"days": RESPONSE_BODY},
            RESPONSE_BODY[0],
            "2026-10-03",
            None,
        ],
    )
    def test_rejects_a_body_that_is_not_a_list(self, bad_body: Any) -> None:
        """Anything other than a JSON array is a validation error."""
        with pytest.raises(ValidationError):
            UserCreatedPerDayResponse.model_validate(bad_body)

    @pytest.mark.parametrize(
        "bad_entry",
        [
            {"date": "2026-10-03"},
            {"count": 3},
            {"day": "2026-10-03", "count": 3},
            {"date": "2026-10-03", "count": "seven"},
        ],
    )
    def test_rejects_entries_that_do_not_match_the_shape(
        self, bad_entry: dict[str, Any]
    ) -> None:
        """One malformed entry fails the whole body."""
        with pytest.raises(ValidationError):
            UserCreatedPerDayResponse.model_validate([bad_entry])

    def test_builds_from_date_objects_as_well_as_strings(self) -> None:
        """Entries produced as date objects serialize to the same body."""
        body = [{"date": date(2026, 10, day), "count": day} for day in range(1, 4)]

        dumped = UserCreatedPerDayResponse.model_validate(body).model_dump()

        assert dumped == [
            {"date": "2026-10-01", "count": 1},
            {"date": "2026-10-02", "count": 2},
            {"date": "2026-10-03", "count": 3},
        ]


class TestAnalyticsSchemasAreReachableFromTheFeaturePackage:
    """Tests for the src/users export of the analytics models."""

    def test_models_are_exported_from_src_users(self) -> None:
        """Both models are importable from the package, not only the module."""
        assert src.users.UserCreatedPerDayEntry is UserCreatedPerDayEntry
        assert src.users.UserCreatedPerDayResponse is UserCreatedPerDayResponse
        assert "UserCreatedPerDayEntry" in src.users.__all__
        assert "UserCreatedPerDayResponse" in src.users.__all__

    def test_exported_models_validate_the_same_body(self) -> None:
        """The package-level names are the working models, not placeholders."""
        response = src.users.UserCreatedPerDayResponse.model_validate(RESPONSE_BODY)

        assert isinstance(response.root[0], src.users.UserCreatedPerDayEntry)
        assert response.model_dump() == RESPONSE_BODY

    def test_the_package_still_exports_its_existing_names(self) -> None:
        """Adding the analytics export did not drop the pre-existing ones."""
        for name in (
            "User",
            "UserCountResponse",
            "UserCreate",
            "UserUpdate",
            "UserPublic",
            "UserList",
            "UserNotFoundError",
            "UserAlreadyExistsError",
        ):
            assert name in src.users.__all__
            assert hasattr(src.users, name)
