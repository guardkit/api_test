"""Analytics integration tests for ``GET /users/created-per-day`` (TASK-A0AE-005).

What sits under this route is pinned elsewhere: the aggregation and its window
in ``test_daily_counts.py`` and ``test_daily_counts_window.py``, the service's
zero-filling in ``test_analytics_service.py``, and the route's wiring in
``test_created_per_day_endpoint.py`` (TASK-A0AE-001 through -004). This file is
the integration layer over all three at once. A request enters through the
ASGI app, the service resolves the window, the CRUD layer counts, and the rows
come back out of a real database — nothing between the HTTP edge and the
``users`` table is replaced or stubbed, which is the whole point of an
integration test: it fails when the halves stop agreeing, even though each half
still passes its own tests.

Four things are pinned, one per acceptance criterion:

* **AC-001** — the answer is exactly seven data points, whether the window held
  twenty-one creations, three, or none.
* **AC-002** — they are ordered oldest day first, the current day last, and
  every count sits on the day its creations happened on.
* **AC-003** — an empty data set answers with seven days of zeros, never with
  an empty array and never with a short one.
* **AC-004** — a POST to the path is refused with 405 and writes nothing; the
  path serves GET and nothing else.

HOW THESE TESTS SAY THE SAME THING AT ANY HOUR, ON ANY DAY. The endpoint takes
no anchor: it measures from the day the request is served. A test that seeded
against a date it had worked out for itself would disagree with the endpoint
the instant the day turned over, so the tests below ask the endpoint what its
window is, sort the days it named — so the rows land on the calendar days they
mean whatever order the endpoint answered in — seed against them, then read the
answer again. The days they assert on are therefore the days the endpoint is
measuring, whatever today happens to be. The single exception is the check that
pins the current day as the last point of the window — a promise about the wall
clock that cannot be checked against the endpoint's own answer — which reads
the clock the way ``test_created_per_day_endpoint.py`` does, and carries the
same caveat: it can only disagree if the day turns over while the request is in
flight.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.main import app
from src.users.models import User

# The route under test, and the length of the window it promises.
ENDPOINT = "/users/created-per-day"
WINDOW_DAYS = 7


def points(response: Response) -> list[dict[str, Any]]:
    """Return the response body as the list of data points it carries.

    Args:
        response: The response from the analytics endpoint.

    Returns:
        One dict per data point, in the order the endpoint sent them.
    """
    body = response.json()
    assert isinstance(body, list)
    return [dict(point) for point in body]


def dates_of(response: Response) -> list[date]:
    """Return the days the endpoint reported, in the order it reported them.

    Args:
        response: The response from the analytics endpoint.

    Returns:
        The window's days, oldest first, as calendar dates.
    """
    return [date.fromisoformat(str(point["date"])) for point in points(response)]


def counts_of(response: Response) -> list[int]:
    """Return the counts the endpoint reported, in the order it reported them.

    Args:
        response: The response from the analytics endpoint.

    Returns:
        One count per data point, oldest day first.
    """
    return [int(point["count"]) for point in points(response)]


def at(day: date, hour: int = 12) -> datetime:
    """Return a naive timestamp on a given day, matching the column's type.

    ``users.created_at`` is a timestamp without time zone (alembic revision
    a143501c5e1f), so rows are written the way the column stores them.

    Args:
        day: The calendar day to place the timestamp on.
        hour: The hour of day to use.

    Returns:
        A naive datetime on that day.
    """
    return datetime(day.year, day.month, day.day, hour, 0, 0)


async def seed_creations(
    db: AsyncSession,
    day: date,
    count: int,
    label: str,
) -> None:
    """Put ``count`` users in the database, all created on the same day.

    Args:
        db: The session to write through.
        day: The calendar day to stamp the creations on.
        count: How many users to create on that day.
        label: Prefix keeping the addresses unique within the test.
    """
    for index in range(count):
        db.add(
            User(
                email=f"{label}-{index}@example.com",
                domain="example.com",
                created_at=at(day),
            )
        )
    await db.flush()


async def seed_one_creation(
    db: AsyncSession,
    day: date,
    label: str,
    deleted_at: datetime | None = None,
) -> None:
    """Put a single user in the database, created on ``day`` and maybe deleted.

    Args:
        db: The session to write through.
        day: The calendar day to stamp the creation on.
        label: The local part of the address, unique within the test.
        deleted_at: A soft-delete timestamp, when the user is deleted.
    """
    db.add(
        User(
            email=f"{label}@example.com",
            domain="example.com",
            created_at=at(day),
            deleted_at=deleted_at,
        )
    )
    await db.flush()


async def user_rows(db: AsyncSession) -> int:
    """Count the rows in the users table, deleted ones included.

    Args:
        db: The session to read through.

    Returns:
        The number of user rows the database holds.
    """
    result = await db.execute(select(func.count()).select_from(User))
    return int(result.scalar_one())


async def window_of(async_client: AsyncClient) -> list[date]:
    """Ask the endpoint which days it is currently measuring.

    Asking rather than computing is what keeps these tests honest across
    midnight: the days seeded are the days the endpoint itself names. Callers
    sort the result before seeding, so the rows go in on the calendar days they
    are meant to land on whatever order the endpoint happened to answer in —
    which is what lets the ordering checks below detect a wrong order instead
    of quietly matching it.

    Args:
        async_client: The client pointed at the application.

    Returns:
        The days of the window as the endpoint reports them.
    """
    response = await async_client.get(ENDPOINT)
    assert response.status_code == HTTPStatus.OK
    days = dates_of(response)
    assert len(days) == WINDOW_DAYS
    return days


class TestSevenDayWindow:
    """AC-001: the series is exactly seven data points long."""

    async def test_a_window_full_of_creations_answers_seven_points(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Three creations on each of the seven days is seven points."""
        days = sorted(await window_of(async_client))
        for index, day in enumerate(days):
            await seed_creations(db_session, day, 3, f"full-{index}")

        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        assert len(points(response)) == WINDOW_DAYS

    async def test_a_partly_populated_window_still_answers_seven_points(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Creations on three days of the window do not shorten it to three.

        The boundary the feature calls out: six days of data is still a
        seven-day answer, because the window is the promise, not the data.
        """
        days = sorted(await window_of(async_client))
        for index, day in enumerate(days[1:4]):
            await seed_creations(db_session, day, 2, f"part-{index}")

        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        assert len(points(response)) == WINDOW_DAYS

    async def test_an_empty_window_still_answers_seven_points(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Nothing in the database is seven points of zero, not an empty body."""
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        assert len(points(response)) == WINDOW_DAYS

    async def test_creations_older_than_the_window_leave_it_at_seven_points(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """A creation before the first day of the window adds a point to none."""
        days = sorted(await window_of(async_client))
        await seed_creations(db_session, days[0] - timedelta(days=5), 4, "ancient")
        await seed_creations(db_session, days[-1], 1, "recent")

        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        assert len(points(response)) == WINDOW_DAYS

    async def test_every_point_carries_a_date_and_a_count(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Each point is exactly ``{"date": "YYYY-MM-DD", "count": int}``."""
        days = sorted(await window_of(async_client))
        await seed_creations(db_session, days[-2], 2, "shape")

        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        for point in points(response):
            assert sorted(point) == ["count", "date"]
            assert isinstance(point["count"], int)
            assert date.fromisoformat(str(point["date"])).isoformat() == point["date"]


class TestOrdering:
    """AC-002: oldest day first, the current day last."""

    async def test_the_days_are_consecutive_and_run_oldest_to_newest(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Each day is the day after the one before it, so the series ascends."""
        days = sorted(await window_of(async_client))
        # Seeded newest day first on purpose: the order of the answer is the
        # endpoint's doing, not the order the rows went into the table.
        for index, day in enumerate(reversed(days)):
            await seed_creations(db_session, day, 1, f"order-{index}")

        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        reported = dates_of(response)
        assert len(reported) == WINDOW_DAYS
        # Every day exactly one after the one before it: ascending, consecutive,
        # no day doubled and no day skipped.
        steps = {
            (later - earlier).days
            for earlier, later in zip(reported, reported[1:], strict=False)
        }
        assert steps == {1}, reported

    async def test_the_window_is_the_seven_days_ending_today(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The last point is the day the request is served on, the first six before."""
        # The one wall-clock read in this file, and the one assertion that
        # cannot be made against the endpoint's own answer: "the current day
        # closes the window" is a promise about today.
        anchor = datetime.now(UTC).date()

        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        reported = dates_of(response)
        assert reported == [
            anchor - timedelta(days=offset) for offset in range(WINDOW_DAYS - 1, -1, -1)
        ]
        assert reported[-1] == anchor

    async def test_each_count_sits_on_the_day_it_was_created_on(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Day one carries nothing, day two one creation, and so on up the week.

        The days are seeded in chronological order with a count that rises with
        them, so the list of counts the endpoint sends back is a fingerprint of
        the order it sent: newest-first, or two days swapped, lands on a
        different list here.
        """
        days = sorted(await window_of(async_client))
        for index, day in enumerate(days):
            await seed_creations(db_session, day, index, f"rising-{index}")

        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        # Day one had nothing to count, day two one creation, and so on: the
        # counts climb with the days, so a series sent newest-first, or with two
        # of the days swapped, lands on a different list here.
        assert counts_of(response) == list(range(WINDOW_DAYS))

    async def test_two_requests_agree_on_the_same_ordered_window(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Asking twice is the same answer both times, in the same order."""
        first = await async_client.get(ENDPOINT)
        second = await async_client.get(ENDPOINT)

        assert first.status_code == HTTPStatus.OK
        assert second.status_code == HTTPStatus.OK
        assert points(second) == points(first)


class TestEmptyDataSet:
    """AC-003: nothing to count is seven days of zeros, not nothing."""

    async def test_an_empty_data_set_answers_with_seven_zero_counts(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """No users at all is the full window, every day reading zero."""
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        assert counts_of(response) == [0] * WINDOW_DAYS
        assert len(dates_of(response)) == WINDOW_DAYS

    async def test_a_day_with_nothing_on_it_reads_zero_between_days_that_have(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """An empty day inside a populated week is a zero, not a missing point."""
        days = sorted(await window_of(async_client))
        await seed_creations(db_session, days[1], 2, "gap-before")
        await seed_creations(db_session, days[3], 1, "gap-after")

        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        assert counts_of(response) == [0, 2, 0, 1, 0, 0, 0]

    async def test_a_soft_deleted_user_leaves_its_day_at_zero(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """A creation that was soft-deleted counts nowhere, so the week reads zero."""
        days = sorted(await window_of(async_client))
        await seed_one_creation(db_session, days[2], "gone", deleted_at=at(days[2], 18))

        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        assert counts_of(response) == [0] * WINDOW_DAYS

    async def test_a_creation_outside_the_window_leaves_the_window_at_zeros(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Creations before the first day of the window are nobody's count."""
        days = sorted(await window_of(async_client))
        await seed_creations(db_session, days[0] - timedelta(days=1), 6, "before")
        await seed_creations(db_session, days[-1] + timedelta(days=1), 6, "after")

        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        assert counts_of(response) == [0] * WINDOW_DAYS


class TestPostIsRejected:
    """AC-004: the path serves GET, and refuses everything else."""

    async def test_a_post_is_refused_with_method_not_allowed(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """POST reaches the path and is turned away with 405, not served."""
        response = await async_client.post(ENDPOINT, json={})

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    async def test_the_refusal_names_get_as_the_only_supported_method(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The refusal says what would have worked: GET, and only GET."""
        response = await async_client.post(ENDPOINT, json={})

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
        assert response.headers["allow"].upper() == "GET"

    async def test_a_refused_post_writes_nothing(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """A request the route refuses does not reach the table."""
        assert await user_rows(db_session) == 0

        response = await async_client.post(
            ENDPOINT, json={"email": "sneaky@example.com"}
        )

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
        assert await user_rows(db_session) == 0

    async def test_the_path_still_serves_get_after_a_refused_post(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Refusing a POST leaves the route itself untouched and readable."""
        refused = await async_client.post(ENDPOINT, json={})
        assert refused.status_code == HTTPStatus.METHOD_NOT_ALLOWED

        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK
        assert len(points(response)) == WINDOW_DAYS

    async def test_the_openapi_contract_declares_no_post(self) -> None:
        """The published contract offers the path as a GET and as nothing else."""
        operations = app.openapi()["paths"][ENDPOINT]

        assert "get" in operations
        assert "post" not in operations
