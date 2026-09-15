"""Tests for the daily user-creation counts: the models and the aggregation.

Two halves, matching the two halves of what TASK-A0AE-001 puts in place:

* the Pydantic data point (``DailyCount``) and entry (``DailyCountResponse``)
  schemas in ``src/users/schemas.py``, and
* the SQLAlchemy aggregation that counts creations per calendar day
  (``crud.daily_count_aggregation_query`` / ``crud.get_daily_counts``).

The seven-day window itself — how many days, which days, and the zero counts
for days nobody registered on — belongs to TASK-A0AE-002 and the endpoint that
follows in TASK-A0AE-003, so nothing here pins it. What is pinned is what must
stay true whatever window is finally asked for: a day is reported as an
ISO8601 string, a count is an integer, one row comes out per day that has
creations, oldest day first, and the same statement means the same thing on
both databases the app runs on.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from src.db.base import DeclarativeBase
from src.users import crud
from src.users.models import User
from src.users.schemas import DailyCount, DailyCountResponse

# An arbitrary week, fixed so the run says the same thing whatever today is.
RANGE_START = date(2026, 1, 5)
RANGE_END = date(2026, 1, 11)


def _day_and_time(day: date, hour: int = 12) -> datetime:
    """Return a naive timestamp on a given day, matching the column's type.

    Args:
        day: The calendar day to place the timestamp on.
        hour: The hour of day to use.

    Returns:
        A naive datetime on that day.
    """
    return datetime(day.year, day.month, day.day, hour, 0, 0)


@contextmanager
def sqlite_users_table() -> Iterator[Engine]:
    """Give a test a throwaway SQLite database holding the app's users table.

    The suite runs against PostgreSQL, which is the database that matters. This
    engine exists beside it for one reason: the day-truncating expression has to
    mean the same thing on SQLite too, and the only way to know that is to ask
    SQLite.

    Yields:
        Engine: A sync engine on an in-memory database with the tables made.
    """
    engine = create_engine("sqlite://")
    DeclarativeBase.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


class TestDailyCountSchema:
    """The individual data point: one day, one count."""

    def test_declares_date_as_a_string_and_count_as_an_int(self) -> None:
        """The data point is a day string and an integer count."""
        fields = DailyCount.model_fields

        assert set(fields) >= {"date", "count"}
        assert fields["date"].annotation is str
        assert fields["count"].annotation is int

    def test_keeps_an_iso8601_date_string_as_given(self) -> None:
        """A day already written in ISO8601 comes back unchanged."""
        point = DailyCount(date="2026-01-07", count=3)

        assert point.date == "2026-01-07"
        assert point.count == 3

    def test_serializes_to_json_with_the_two_fields(self) -> None:
        """The data point serializes as the pair the response is built from."""
        payload = DailyCount(date="2026-01-07", count=3).model_dump()

        assert payload == {"date": "2026-01-07", "count": 3}

    def test_json_schema_types(self) -> None:
        """OpenAPI sees a string day and an integer count."""
        properties = DailyCount.model_json_schema()["properties"]

        assert properties["date"]["type"] == "string"
        assert properties["count"]["type"] == "integer"

    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            (date(2026, 1, 7), "2026-01-07"),
            (datetime(2026, 1, 7, 23, 59, 59), "2026-01-07"),
            (datetime(2026, 1, 7, 23, 59, 59, tzinfo=UTC), "2026-01-07"),
            # 18:30 at UTC+6 is 12:30 on the same UTC day: the UTC day is the
            # one reported, whatever offset the caller wrote the day in.
            (
                datetime(2026, 1, 7, 18, 30, tzinfo=timezone(timedelta(hours=6))),
                "2026-01-07",
            ),
            ("2026-01-07T00:00:00", "2026-01-07"),
            ("2026-01-07T23:59:59.999999", "2026-01-07"),
            ("2026-01-07T12:00:00Z", "2026-01-07"),
        ],
    )
    def test_normalizes_any_day_shape_to_an_iso8601_date_string(
        self, given: date | datetime | str, expected: str
    ) -> None:
        """A date, a datetime or an ISO8601 timestamp all land on one day."""
        assert DailyCount(date=given, count=1).date == expected

    @pytest.mark.parametrize(
        "given",
        ["not-a-date", "07/01/2026", "2026-13-07", "", "yesterday"],
    )
    def test_rejects_a_day_that_is_not_iso8601(self, given: str) -> None:
        """A day nobody can read as ISO8601 is refused, not passed through."""
        with pytest.raises(ValidationError) as exc_info:
            DailyCount(date=given, count=1)

        assert "date" in str(exc_info.value)

    def test_rejects_a_count_that_is_not_a_number(self) -> None:
        """A count has to be a count."""
        with pytest.raises(ValidationError) as exc_info:
            DailyCount(date="2026-01-07", count="five")  # type: ignore[arg-type]

        assert "count" in str(exc_info.value)

    def test_a_series_of_data_points_round_trips(self) -> None:
        """Data points are the unit a series is built from, in any length."""
        given = [
            {"date": "2026-01-05", "count": 1},
            {"date": "2026-01-06", "count": 0},
            {"date": "2026-01-07", "count": 2},
        ]
        series = [DailyCount(**item) for item in given]

        assert [item.model_dump() for item in series] == given

    def test_examples_are_valid_for_the_model(self) -> None:
        """The example shown in the docs validates against the model itself."""
        extra = DailyCount.model_config.get("json_schema_extra")
        assert isinstance(extra, Mapping)
        for example in extra["examples"]:
            assert DailyCount(**example).model_dump() == example


class TestDailyCountResponseSchema:
    """The response entry: a day and a count, in the documented shape."""

    def test_declares_date_as_a_string_and_count_as_an_int(self) -> None:
        """The response entry carries the day and the count the task names."""
        fields = DailyCountResponse.model_fields

        assert set(fields) >= {"date", "count"}
        assert fields["date"].annotation is str
        assert fields["count"].annotation is int

    def test_keeps_an_iso8601_date_string_as_given(self) -> None:
        """A day already written in ISO8601 comes back unchanged."""
        entry = DailyCountResponse(date="2026-01-07", count=5)

        assert entry.date == "2026-01-07"
        assert entry.count == 5

    def test_serializes_to_json_with_the_two_fields(self) -> None:
        """The entry serializes to exactly the documented pair of fields."""
        payload = DailyCountResponse(date="2026-01-07", count=5).model_dump()

        assert payload == {"date": "2026-01-07", "count": 5}

    def test_json_schema_types(self) -> None:
        """OpenAPI sees a string day and an integer count."""
        properties = DailyCountResponse.model_json_schema()["properties"]

        assert properties["date"]["type"] == "string"
        assert properties["count"]["type"] == "integer"

    @pytest.mark.parametrize(
        "given",
        [date(2026, 1, 7), datetime(2026, 1, 7, 8, 30), "2026-01-07T08:30:00"],
    )
    def test_normalizes_the_day_to_an_iso8601_date_string(
        self, given: date | datetime | str
    ) -> None:
        """Whatever shape the day arrives in, the response says ISO8601."""
        assert DailyCountResponse(date=given, count=1).date == "2026-01-07"

    def test_rejects_a_day_that_is_not_iso8601(self) -> None:
        """A day nobody can read as ISO8601 is refused."""
        with pytest.raises(ValidationError):
            DailyCountResponse(date="01-07-2026", count=1)

    def test_rejects_a_count_that_is_not_a_number(self) -> None:
        """A count has to be a count."""
        with pytest.raises(ValidationError):
            DailyCountResponse(date="2026-01-07", count="five")  # type: ignore[arg-type]

    def test_examples_are_valid_for_the_model(self) -> None:
        """The example shown in the docs validates against the model itself."""
        extra = DailyCountResponse.model_config.get("json_schema_extra")
        assert isinstance(extra, Mapping)
        for example in extra["examples"]:
            assert DailyCountResponse(**example).model_dump() == example


async def seed_user(
    db: AsyncSession,
    email: str,
    created_at: datetime,
    deleted_at: datetime | None = None,
) -> None:
    """Put one user in the database with a chosen creation time.

    Args:
        db: The session to write through.
        email: The address, unique across the test.
        created_at: The creation timestamp to store.
        deleted_at: A soft-delete timestamp, when the user is deleted.
    """
    db.add(
        User(
            email=email,
            domain=email.split("@")[-1],
            created_at=created_at,
            deleted_at=deleted_at,
        )
    )
    await db.flush()


class TestDailyCountAggregation:
    """The aggregation query: one row per day that has creations."""

    async def test_counts_each_day_in_the_range_separately(
        self, db_session: AsyncSession
    ) -> None:
        """Two days with creations come back as two data points with two counts."""
        await seed_user(db_session, "a1@day-one.test", _day_and_time(RANGE_START))
        await seed_user(db_session, "a2@day-one.test", _day_and_time(RANGE_START, 18))
        await seed_user(
            db_session, "b1@day-two.test", _day_and_time(RANGE_START + timedelta(1))
        )

        counts = await crud.get_daily_counts(db_session, RANGE_START, RANGE_END)

        assert [item.model_dump() for item in counts] == [
            {"date": "2026-01-05", "count": 2},
            {"date": "2026-01-06", "count": 1},
        ]
        assert all(isinstance(item, DailyCount) for item in counts)

    async def test_days_come_back_oldest_first_whatever_the_insert_order(
        self, db_session: AsyncSession
    ) -> None:
        """Ordering belongs to the query, not to the order rows were written in."""
        await seed_user(
            db_session,
            "newest@analytics.test",
            _day_and_time(RANGE_START + timedelta(4)),
        )
        await seed_user(
            db_session,
            "middle@analytics.test",
            _day_and_time(RANGE_START + timedelta(2)),
        )
        await seed_user(db_session, "oldest@analytics.test", _day_and_time(RANGE_START))

        days = [
            item.date
            for item in await crud.get_daily_counts(db_session, RANGE_START, RANGE_END)
        ]

        assert days == ["2026-01-05", "2026-01-07", "2026-01-09"]

    async def test_the_range_is_closed_at_both_ends(
        self, db_session: AsyncSession
    ) -> None:
        """The first and last day of the range are counted in full."""
        await seed_user(db_session, "first@bounds.test", _day_and_time(RANGE_START, 0))
        await seed_user(
            db_session,
            "last@bounds.test",
            datetime(RANGE_END.year, RANGE_END.month, RANGE_END.day, 23, 59, 59),
        )

        counts = await crud.get_daily_counts(db_session, RANGE_START, RANGE_END)

        assert [item.model_dump() for item in counts] == [
            {"date": "2026-01-05", "count": 1},
            {"date": "2026-01-11", "count": 1},
        ]

    async def test_creations_outside_the_range_are_left_out(
        self, db_session: AsyncSession
    ) -> None:
        """A day before the range and a day after it are not reported."""
        await seed_user(
            db_session,
            "before@bounds.test",
            _day_and_time(RANGE_START - timedelta(1)),
        )
        await seed_user(
            db_session, "inside@bounds.test", _day_and_time(RANGE_START + timedelta(1))
        )
        await seed_user(
            db_session, "after@bounds.test", _day_and_time(RANGE_END + timedelta(1))
        )

        counts = await crud.get_daily_counts(db_session, RANGE_START, RANGE_END)

        assert [item.model_dump() for item in counts] == [
            {"date": "2026-01-06", "count": 1}
        ]

    async def test_soft_deleted_users_are_left_out(
        self, db_session: AsyncSession
    ) -> None:
        """A deleted registration is not a creation anyone still counts."""
        await seed_user(db_session, "kept@deleted.test", _day_and_time(RANGE_START))
        await seed_user(
            db_session,
            "gone@deleted.test",
            _day_and_time(RANGE_START),
            deleted_at=datetime(2026, 2, 1, 9, 0, 0),
        )

        counts = await crud.get_daily_counts(db_session, RANGE_START, RANGE_END)

        assert [item.model_dump() for item in counts] == [
            {"date": "2026-01-05", "count": 1}
        ]

    def test_the_statement_is_selectable_on_its_own(self) -> None:
        """The builder hands back a statement, not a result.

        The statement has to render on both databases the app runs on; whether
        it means the same thing on both is what the execution checks here and
        in TestDailyCountAggregationAcrossDialects are for.
        """
        from sqlalchemy.dialects import postgresql, sqlite
        from sqlalchemy.sql import Select

        statement = crud.daily_count_aggregation_query(RANGE_START, RANGE_END)

        assert isinstance(statement, Select)
        for dialect in (postgresql.dialect(), sqlite.dialect()):
            assert str(statement.compile(dialect=dialect))


class TestDailyCountAggregationAcrossDialects:
    """The same statement, asked of SQLite as well as of PostgreSQL.

    The suite runs against PostgreSQL. These checks put the same statement in
    front of SQLite too, because that is the database a developer's plain
    ``pytest`` and a bare ``uvicorn`` fall back to, and because the two hand
    back a day as different Python types — a ``date`` there, the ``YYYY-MM-DD``
    text here.
    """

    def test_days_are_counted_the_same_way_on_sqlite(self) -> None:
        """SQLite reads the day-truncating expression the same way PostgreSQL does."""
        with sqlite_users_table() as engine:
            with sessionmaker(bind=engine)() as session:
                session.add_all(
                    [
                        User(
                            email="a1@sqlite.test",
                            domain="sqlite.test",
                            created_at=_day_and_time(RANGE_START),
                        ),
                        User(
                            email="a2@sqlite.test",
                            domain="sqlite.test",
                            created_at=_day_and_time(RANGE_START, 22),
                        ),
                        User(
                            email="b1@sqlite.test",
                            domain="sqlite.test",
                            created_at=_day_and_time(RANGE_START + timedelta(1)),
                        ),
                        User(
                            email="out@sqlite.test",
                            domain="sqlite.test",
                            created_at=_day_and_time(RANGE_END + timedelta(1)),
                        ),
                    ]
                )
                session.commit()

                rows: Sequence[Mapping[str, Any]] = (
                    session.execute(
                        crud.daily_count_aggregation_query(RANGE_START, RANGE_END)
                    )
                    .mappings()
                    .all()
                )

            points = [
                DailyCount(date=str(row["day"]), count=row["count"]) for row in rows
            ]

        assert [point.model_dump() for point in points] == [
            {"date": "2026-01-05", "count": 2},
            {"date": "2026-01-06", "count": 1},
        ]

    def test_a_sqlite_day_and_a_postgresql_day_normalize_identically(self) -> None:
        """One day read from either database yields one and the same string."""
        from src.users.schemas import to_iso_date

        as_text = "2026-01-07"  # what SQLite's date() hands back
        as_date = date(2026, 1, 7)  # what PostgreSQL's date() hands back

        assert to_iso_date(as_text) == to_iso_date(as_date) == "2026-01-07"
        assert DailyCount(date=to_iso_date(as_text), count=1) == DailyCount(
            date=to_iso_date(as_date), count=1
        )
