"""Schema tests for the daily user-creation counts (TASK-D49B-001).

AC-001 — DailyUserCount, the ``(date, count)`` entry of the daily count
response.
AC-002 — SingleDayUserCountResponse, the response describing a single day.

These tests pin the two schemas themselves: what they accept, what they
reject, and the JSON they produce.  Nothing here touches the database or the
HTTP layer, because the query is TASK-D49B-002's, the route is
TASK-D49B-003's, the endpoint is TASK-D49B-004's and the endpoint tests are
TASK-D49B-005's — so no test in this file changes when those land.  Every
instant used is fixed, so no test here reads the host clock or the
environment.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from src.users.schemas import DailyUserCount, SingleDayUserCountResponse

# A day and its count, used throughout.  Fixed so no test depends on today.
A_DAY = date(2026, 7, 9)
A_DAY_ISO = "2026-07-09"


def _schemas() -> list[type[BaseModel]]:
    """Return both daily-count schemas, for the tests that apply to each."""
    return [DailyUserCount, SingleDayUserCountResponse]


class TestDailyUserCountSchema:
    """AC-001: the (date, count) entry of the daily count response."""

    def test_is_a_pydantic_model(self) -> None:
        """The schema is a Pydantic model, so FastAPI can use it directly."""
        assert issubclass(DailyUserCount, BaseModel)
        assert "date" in DailyUserCount.model_fields
        assert "count" in DailyUserCount.model_fields

    def test_accepts_an_iso_8601_date_string(self) -> None:
        """A date given as ISO-8601 text is read as that calendar day."""
        entry = DailyUserCount(date=A_DAY_ISO, count=5)

        assert entry.date == A_DAY
        assert entry.count == 5

    def test_accepts_a_date_object(self) -> None:
        """A plain date object is accepted unchanged."""
        entry = DailyUserCount(date=A_DAY, count=0)

        assert entry.date == A_DAY
        assert entry.count == 0

    def test_serializes_to_a_date_and_count_pair(self) -> None:
        """The wire form is the date as ISO text alongside the count."""
        payload = DailyUserCount(date=A_DAY, count=5).model_dump()

        assert payload["date"] == A_DAY
        assert payload["count"] == 5
        assert payload["date"].isoformat() == A_DAY_ISO
        assert "date" in payload
        assert "count" in payload

    def test_json_form_carries_the_date_as_iso_text(self) -> None:
        """JSON serialisation keeps the date in ISO-8601 form."""
        json_text = DailyUserCount(date=A_DAY, count=3).model_dump_json()

        assert f'"{A_DAY_ISO}"' in json_text
        assert '"count"' in json_text

    def test_round_trips_through_json(self) -> None:
        """What the schema writes, the schema reads back unchanged."""
        entry = DailyUserCount(date=A_DAY, count=7)

        assert DailyUserCount.model_validate_json(entry.model_dump_json()) == entry

    def test_a_day_with_no_new_users_is_valid(self) -> None:
        """A count of zero is a valid entry, which is how an empty day reads."""
        entry = DailyUserCount(date=A_DAY, count=0)

        assert entry.count == 0

    @pytest.mark.parametrize("count", [-1, -100])
    def test_rejects_a_negative_count(self, count: int) -> None:
        """A count cannot be negative: no day has fewer than zero new users."""
        with pytest.raises(ValidationError):
            DailyUserCount(date=A_DAY, count=count)

    @pytest.mark.parametrize(
        "date_value", ["", "not-a-date", "07/09/2026", "2026-13-01"]
    )
    def test_rejects_an_unparsable_date(self, date_value: str) -> None:
        """Text that is not a date or a timestamp is refused, not guessed."""
        with pytest.raises(ValidationError):
            DailyUserCount(date=date_value, count=1)

    @pytest.mark.parametrize("count", ["", "five", [], 2.5])
    def test_rejects_a_count_that_is_not_a_whole_number(self, count: Any) -> None:
        """A count has to be a whole number."""
        with pytest.raises(ValidationError):
            DailyUserCount(date=A_DAY, count=count)

    def test_both_fields_are_required(self) -> None:
        """Neither the day nor the count may be left out."""
        with pytest.raises(ValidationError):
            DailyUserCount(count=1)  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            DailyUserCount(date=A_DAY)  # type: ignore[call-arg]

    @pytest.mark.parametrize(
        ("moment", "expected"),
        [
            # Aware timestamps are read in UTC, wherever the run happens.
            (datetime(2026, 7, 9, 23, 30, tzinfo=UTC), date(2026, 7, 9)),
            (
                datetime(2026, 7, 9, 1, 30, tzinfo=timezone(timedelta(hours=-7))),
                date(2026, 7, 9),
            ),
            (
                datetime(2026, 7, 10, 2, 0, tzinfo=timezone(timedelta(hours=4))),
                date(2026, 7, 9),
            ),
            # A naive timestamp is taken as stamped, as the rest of this
            # package reads a day out of a timestamp.
            (datetime(2026, 7, 9, 23, 59, 59), date(2026, 7, 9)),
        ],
    )
    def test_a_timestamp_names_the_day_it_falls_on(
        self, moment: datetime, expected: date
    ) -> None:
        """A creation timestamp may stand in for the day, which it reduces to."""
        assert DailyUserCount(date=moment, count=1).date == expected

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            (f"{A_DAY_ISO}T23:30:00Z", A_DAY),
            ("2026-07-10T02:00:00+04:00", date(2026, 7, 9)),
            ("2026-07-09 23:59:59", A_DAY),
            (A_DAY_ISO, A_DAY),
        ],
    )
    def test_a_timestamp_text_names_the_day_it_falls_on(
        self, text: str, expected: date
    ) -> None:
        """A driver that hands back timestamp text gets the same day."""
        assert DailyUserCount(date=text, count=1).date == expected

    def test_json_schema_describes_the_pair(self) -> None:
        """The published schema documents the two fields and their rules."""
        schema = DailyUserCount.model_json_schema()

        assert set(schema["required"]) == {"date", "count"}
        assert schema["properties"]["date"]["type"] == "string"
        assert schema["properties"]["date"]["format"] == "date"
        assert schema["properties"]["count"]["type"] == "integer"
        assert schema["properties"]["count"]["minimum"] == 0


class TestSingleDayUserCountResponseSchema:
    """AC-002: the response for a single day."""

    def test_is_a_pydantic_model(self) -> None:
        """The schema is a Pydantic model, so FastAPI can use it directly."""
        assert issubclass(SingleDayUserCountResponse, BaseModel)
        assert "date" in SingleDayUserCountResponse.model_fields
        assert "count" in SingleDayUserCountResponse.model_fields

    def test_carries_the_day_and_its_count(self) -> None:
        """A single-day response reads as the day and how many joined it."""
        response = SingleDayUserCountResponse(date=A_DAY_ISO, count=4)

        assert response.date == A_DAY
        assert response.count == 4

    def test_serializes_to_a_date_and_count_pair(self) -> None:
        """The wire form is the date as ISO text alongside the count."""
        payload = SingleDayUserCountResponse(date=A_DAY, count=4).model_dump()

        assert payload["date"].isoformat() == A_DAY_ISO
        assert payload["count"] == 4

    def test_round_trips_through_json(self) -> None:
        """What the schema writes, the schema reads back unchanged."""
        response = SingleDayUserCountResponse(date=A_DAY, count=0)

        assert (
            SingleDayUserCountResponse.model_validate_json(response.model_dump_json())
            == response
        )

    def test_a_timestamp_names_the_day_it_falls_on(self) -> None:
        """A timestamp for the single day reduces to that day, in UTC."""
        moment = datetime(2026, 7, 10, 2, 0, tzinfo=timezone(timedelta(hours=4)))

        assert SingleDayUserCountResponse(date=moment, count=1).date == date(2026, 7, 9)

    @pytest.mark.parametrize("payload", [{"date": A_DAY_ISO}, {"count": 2}])
    def test_both_fields_are_required(self, payload: dict[str, Any]) -> None:
        """Neither the day nor the count may be left out."""
        with pytest.raises(ValidationError):
            SingleDayUserCountResponse(**payload)

    @pytest.mark.parametrize("count", [-1, "five", 2.5])
    def test_rejects_a_count_that_is_not_a_whole_number_of_people(
        self, count: Any
    ) -> None:
        """The count is a whole number of people, never negative."""
        with pytest.raises(ValidationError):
            SingleDayUserCountResponse(date=A_DAY, count=count)

    def test_a_single_day_is_also_a_daily_count_entry(self) -> None:
        """One day's response is a valid entry of the multi-day array."""
        response = SingleDayUserCountResponse(date=A_DAY, count=2)

        assert DailyUserCount.model_validate(response.model_dump()) == DailyUserCount(
            date=A_DAY, count=2
        )

    def test_a_daily_count_entry_is_also_a_single_day_response(self) -> None:
        """One entry of the array reads back as a single-day response."""
        entry = DailyUserCount(date=A_DAY, count=2)

        assert SingleDayUserCountResponse.model_validate(
            entry.model_dump()
        ) == SingleDayUserCountResponse(date=A_DAY, count=2)

    def test_json_schema_describes_the_pair(self) -> None:
        """The published schema documents the two fields and their rules."""
        schema = SingleDayUserCountResponse.model_json_schema()

        assert set(schema["required"]) == {"date", "count"}
        assert schema["properties"]["date"]["type"] == "string"
        assert schema["properties"]["date"]["format"] == "date"
        assert schema["properties"]["count"]["type"] == "integer"
        assert schema["properties"]["count"]["minimum"] == 0


class TestBothDailyCountSchemas:
    """Rules that hold of either daily-count shape."""

    @pytest.mark.parametrize("schema", _schemas())
    def test_documents_an_example_of_the_pair(self, schema: type[BaseModel]) -> None:
        """Each schema carries a documented example, as this repo's schemas do."""
        extra = schema.model_config.get("json_schema_extra")
        assert isinstance(extra, Mapping)
        examples = extra["examples"]

        assert isinstance(examples, list)
        assert examples, schema.__name__
        for example in examples:
            assert isinstance(example, Mapping)
            assert {"date", "count"} <= set(example)

    @pytest.mark.parametrize("schema", _schemas())
    def test_a_list_of_days_carries_the_pair_repeatedly(
        self, schema: type[BaseModel]
    ) -> None:
        """A list of these entries serialises as the endpoint's JSON array."""
        days = [schema(date=date(2026, 7, day), count=day) for day in range(1, 8)]

        dumped = [entry.model_dump() for entry in days]

        assert len(dumped) == 7
        assert all({"date", "count"} <= set(entry) for entry in dumped)
        assert [entry["count"] for entry in dumped] == list(range(1, 8))
