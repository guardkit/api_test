"""Integration tests for ``GET /users/created-per-day`` (TASK-6F3D-005).

Every scenario of
``features/get-users-created-per-day/get-users-created-per-day.feature`` is
graded here end to end: the request enters the ASGI application, crosses the
middleware stack, reaches the analytics router, the service, the query layer and
a real database, and the JSON that comes back is read as a stranger would read
it — decoded text, not internal objects. Nothing inside ``src`` is called
directly except the users feature's public write interface, which is how the
rows get into the table in the first place.

WHAT MAKES THESE INTEGRATION RATHER THAN UNIT TESTS
    The unit tests of this feature grade the pieces separately —
    ``test_created_per_day_schemas.py`` the contract,
    ``test_created_per_day_crud.py`` the query,
    ``test_created_per_day_service.py`` the window arithmetic,
    ``test_created_per_day_router.py`` the handler. What only an integration
    test can catch is a piece that is right on its own and wrong in sequence: a
    route registered after ``GET /users/{user_id}`` and therefore read as a
    user id, a session injected that is not the session the rows were written
    through, a serializer that turns a correct ``date`` into something else.
    Each test below therefore goes through HTTP against the database this run
    was settled on (in-memory SQLite by default, PostgreSQL under
    ``qa/run-suite.sh`` — see ``tests/__init__.py``), and the assertions are
    about the reply a caller sees.

WHY THE WINDOW IS READ FROM THE RESPONSE BEFORE ANY ROW IS WRITTEN
    The window is the seven UTC days ending today, so a test that computed
    "today" on the test side could disagree with the application across a UTC
    midnight crossing — a difference that has nothing to do with the code under
    test. So the tests that need the window ask the endpoint for it first
    (``served_window``) and seed relative to what it answered, and the tests
    that pin "today" bracket the request with the clock before and after it
    (``assert_window_ends_today``). The tests are then deterministic at every
    hour of every day, which is what makes them safe to run in a suite that
    runs at any hour.

WHAT IS DELIBERATELY NOT ASSERTED
    The behaviour of PUT and DELETE on this path is not pinned. Those requests
    fall through to ``GET``-less routes belonging to the *users* feature
    (``/users/{user_id}``), so what they answer is that feature's routing, not
    this feature's promise, and pinning it would freeze a boundary this feature
    does not own. The feature spec asks only that POST be rejected, and that is
    what AC-005 grades.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from itertools import pairwise
from pathlib import Path

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.analytics.schemas import CreatedPerDayResponse
from src.users import crud
from src.users.schemas import UserCreate

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: The endpoint under test, served by ``src/analytics/router.py``.
ENDPOINT = "/users/created-per-day"

#: The file TASK-6F3D-005 writes. AC-008 grades exactly this list.
MODIFIED_FILES = ("tests/analytics/test_created_per_day_integration.py",)

#: Days in the window the endpoint promises, restated here from the feature
#: spec ("Must return exactly 7 data points") so the tests fail if the
#: implementation quietly widens or narrows it.
WINDOW_DAYS = 7


def utc_today() -> date:
    """Today's UTC calendar day, read from the clock rather than from ``src``.

    Deriving it here rather than importing ``src.analytics.crud.utc_today``
    keeps the tests from grading the implementation against itself.

    Returns:
        date: The current UTC calendar day.
    """
    return datetime.now(tz=UTC).date()


def at_noon(day: date) -> datetime:
    """A timestamp in the middle of a day, so no window edge is being probed.

    Args:
        day: The calendar day to place the timestamp on.

    Returns:
        datetime: Noon on ``day``, naive, the way ``users.created_at`` stores
        UTC timestamps.
    """
    return datetime(day.year, day.month, day.day, 12, 0)


def email_for(tag: str, index: int, day: date) -> str:
    """The address ``seed_users_on_day`` gives to one of its rows.

    Args:
        tag: The seeding call's prefix.
        index: Which of that call's rows this is.
        day: The day the row was stamped with.

    Returns:
        str: A unique email address, so a test can find a row it seeded again.
    """
    return f"{tag}-{index}-{day.isoformat()}@example.com"


async def seed_users_on_day(db: AsyncSession, tag: str, day: date, count: int) -> None:
    """Create ``count`` users whose creation timestamp falls on ``day``.

    Rows go in through the users feature's public write interface, which is
    what a real caller would do; only the timestamp is then moved, because the
    window under test spans days and a row cannot be written "in the past" by
    asking the API to.

    Args:
        db: The session to write through — the very session the endpoint reads,
            which is part of what these tests check.
        tag: Prefix for the generated email addresses, so seeding the same day
            twice does not collide on the unique email.
        day: The calendar day to stamp the rows with.
        count: How many users to create.
    """
    for index in range(count):
        user = await crud.create_user(
            db,
            UserCreate(
                email=email_for(tag, index, day),
                full_name="Seeded",
            ),
        )
        user.created_at = at_noon(day)
        await db.flush()


def dates_of(body: object) -> list[date]:
    """The data points' dates, in the order the response sent them.

    Args:
        body: The decoded response body, which must be a list of data points.

    Returns:
        list[date]: One date per data point, oldest first if the endpoint kept
        its promise.

    Raises:
        AssertionError: If the body is not a JSON array of ``{date, count}``
            objects, which is itself a breach of the contract.
    """
    assert isinstance(body, list), f"the body must be a JSON array, got {body!r}"
    return [date.fromisoformat(point["date"]) for point in body]


def counts_by_day(body: object) -> dict[date, int]:
    """The reply as a day-to-count mapping, for assertions about contents.

    Args:
        body: The decoded response body.

    Returns:
        dict[date, int]: Each answered day with the count that came with it.

    Raises:
        AssertionError: If the body is not a JSON array of objects, which is
            itself a breach of the contract.
    """
    assert isinstance(body, list), f"the body must be a JSON array, got {body!r}"
    for point in body:
        assert isinstance(point, dict), f"a data point must be an object, got {point!r}"
    return {date.fromisoformat(point["date"]): point["count"] for point in body}


async def served_window(async_client: AsyncClient) -> list[date]:
    """Ask the endpoint which days it currently considers the window.

    Probing the window instead of computing it locally is what keeps the
    seeding below inside the window even if UTC midnight is crossed mid-test.

    Args:
        async_client: The HTTP client bound to the application.

    Returns:
        list[date]: The days of the window as the endpoint itself reported
        them, oldest first.
    """
    response = await async_client.get(ENDPOINT)
    assert response.status_code == HTTPStatus.OK, response.text
    return dates_of(response.json())


def assert_window_ends_today(days: list[date], *, before: date, after: date) -> None:
    """Check the window is the seven UTC days ending on the running today.

    ``before`` and ``after`` bracket the request, so a clock that crossed
    midnight while the request was in flight still satisfies the promise.

    Args:
        days: The dates the endpoint answered, oldest first.
        before: The UTC day before the request was made.
        after: The UTC day after the request was made.
    """
    assert days[-1] in {before, after}, (
        f"the newest day must be today (UTC); the request ran on "
        f"{before.isoformat()}..{after.isoformat()} but answered "
        f"{days[-1].isoformat()}"
    )
    assert days[0] == days[-1] - timedelta(days=WINDOW_DAYS - 1), (
        f"the window must span {WINDOW_DAYS} consecutive days, got "
        f"{days[0].isoformat()}..{days[-1].isoformat()}"
    )


def _tool(name: str) -> list[str]:
    """The command line that runs a project-configured tool.

    Args:
        name: The tool's executable name, e.g. ``"ruff"``.

    Returns:
        list[str]: The command, preferring the project's own virtualenv.
    """
    local = PROJECT_ROOT / ".venv" / "bin" / name
    if local.exists():
        return [str(local)]
    return [sys.executable, "-m", name]  # pragma: no cover - fallback


def json_body(response: Response) -> object:
    """Decode a response body with the standard library, not with httpx.

    Going through ``json.loads`` rather than ``response.json()`` is the point:
    it proves the bytes on the wire are JSON, not merely that a parser somewhere
    in the test client could make an object out of them.

    Args:
        response: The response to read.

    Returns:
        object: Whatever the body decodes to.
    """
    return json.loads(response.content.decode("utf-8"))


class TestHappyPathSevenDaysOfData:
    """AC-001: a request returns the last 7 days of data.

    Scenario "A request to the daily counts endpoint returns the last 7 days of
    data" — the request succeeds, carries seven data points ordered oldest to
    newest, each with an ISO-8601 date and a non-negative integer count.
    """

    async def test_get_succeeds_and_answers_seven_data_points(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """A plain GET to the endpoint succeeds with seven data points."""
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK, response.text
        assert len(response.json()) == WINDOW_DAYS

    async def test_seeded_creations_land_on_the_day_they_happened(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """The reply reports the rows that were written, on their own days.

        This is the integration claim the unit tests cannot make: a row written
        through the users feature is visible to the analytics endpoint, on the
        day it falls, with the right count, through the whole stack.
        """
        window = await served_window(async_client)
        older, newer = window[1], window[-2]
        await seed_users_on_day(db_session, "older", older, 3)
        await seed_users_on_day(db_session, "newer", newer, 2)

        response = await async_client.get(ENDPOINT)
        assert response.status_code == HTTPStatus.OK, response.text
        counts = counts_by_day(response.json())
        assert counts[older] == 3
        assert counts[newer] == 2
        untouched = {
            day: count for day, count in counts.items() if day not in (older, newer)
        }
        assert set(untouched.values()) == {0}, (
            f"days with no seeded creation must read as zero, got {untouched}"
        )

    async def test_the_window_is_the_seven_utc_days_ending_today(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The days answered are today (UTC) and the six days before it."""
        before = utc_today()
        response = await async_client.get(ENDPOINT)
        after = utc_today()

        assert response.status_code == HTTPStatus.OK, response.text
        assert_window_ends_today(dates_of(response.json()), before=before, after=after)

    async def test_every_data_point_has_an_iso_date_and_a_non_negative_count(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Dates are ``YYYY-MM-DD`` text, counts are integers of zero or more."""
        window = await served_window(async_client)
        await seed_users_on_day(db_session, "shaped", window[-1], 2)

        response = await async_client.get(ENDPOINT)
        body = response.json()
        assert isinstance(body, list)
        for point in body:
            assert isinstance(point["date"], str)
            assert len(point["date"]) == len("2026-09-14")
            assert date.fromisoformat(point["date"]).isoformat() == point["date"]
            assert isinstance(point["count"], int)
            assert not isinstance(point["count"], bool)
            assert point["count"] >= 0

    async def test_the_path_is_served_by_analytics_not_by_the_user_id_route(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """``created-per-day`` is not swallowed as a user id.

        ``src/users/router.py`` serves ``GET /users/{user_id}`` and rejects a
        non-UUID id, so if the analytics router were registered after it this
        request would answer 400 or 404 instead of the series. The ordering is
        a wiring fact in ``src/main.py``, invisible from either router's own
        tests.
        """
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK, response.text
        assert isinstance(response.json(), list)
        assert "valid UUID" not in response.text


class TestExactlySevenDataPoints:
    """AC-002: exactly 7 days are returned, whatever the history holds.

    Scenario "The endpoint returns exactly 7 days of data regardless of total
    history".
    """

    async def test_exactly_seven_days_when_nothing_was_ever_created(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """An untouched database still answers seven data points."""
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK, response.text
        assert len(response.json()) == WINDOW_DAYS

    @pytest.mark.parametrize("days_back", [0, 1, 6, 7, 8, 20, 40])
    async def test_exactly_seven_days_whatever_the_history(
        self,
        days_back: int,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Rows inside the window, on its edge, and far outside it all answer
        seven data points — the count of days is the contract, not the data."""
        window = await served_window(async_client)
        await seed_users_on_day(
            db_session, f"back-{days_back}", window[-1] - timedelta(days=days_back), 3
        )

        response = await async_client.get(ENDPOINT)
        assert response.status_code == HTTPStatus.OK, response.text
        assert len(response.json()) == WINDOW_DAYS

    async def test_exactly_seven_days_when_every_day_of_the_window_has_rows(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """A fully populated window answers seven points, not one per row."""
        window = await served_window(async_client)
        for offset, day in enumerate(window):
            await seed_users_on_day(db_session, f"full-{offset}", day, 2)

        response = await async_client.get(ENDPOINT)
        assert len(response.json()) == WINDOW_DAYS


class TestNeverMoreThanSevenDataPoints:
    """AC-003: no more than 7 days are ever returned.

    Scenario "The endpoint does not return more than 7 days of data".
    """

    async def test_history_far_outside_the_window_does_not_lengthen_the_reply(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Rows spread over six weeks still answer seven days, not forty."""
        window = await served_window(async_client)
        for weeks_back in range(1, 7):
            await seed_users_on_day(
                db_session,
                f"weeks-{weeks_back}",
                window[-1] - timedelta(days=weeks_back * 7),
                2,
            )

        response = await async_client.get(ENDPOINT)
        assert response.status_code == HTTPStatus.OK, response.text
        body = response.json()
        assert isinstance(body, list)
        assert len(body) <= WINDOW_DAYS
        assert len(body) == WINDOW_DAYS

    async def test_no_data_point_reaches_outside_the_seven_day_window(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Nothing older than six days ago, and nothing from the future.

        A length-7 assertion alone would pass for a window slid off today; this
        pins where the seven days are allowed to sit.
        """
        window = await served_window(async_client)
        for offset in (0, 3, 9, 15):
            await seed_users_on_day(
                db_session, f"spread-{offset}", window[-1] - timedelta(days=offset), 1
            )

        before = utc_today()
        response = await async_client.get(ENDPOINT)
        after = utc_today()

        assert response.status_code == HTTPStatus.OK, response.text
        days = dates_of(response.json())
        assert len(days) <= WINDOW_DAYS
        oldest_allowed = before - timedelta(days=WINDOW_DAYS - 1)
        assert min(days) >= oldest_allowed, (
            f"the reply reaches older than the {WINDOW_DAYS}-day window: "
            f"{min(days).isoformat()} precedes {oldest_allowed.isoformat()}"
        )
        assert max(days) <= after, (
            f"the reply reaches a future day: {max(days).isoformat()} follows "
            f"{after.isoformat()}"
        )

    async def test_reading_the_endpoint_repeatedly_answers_the_same_days(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The endpoint is a read: repeating it neither grows nor shifts it."""
        first = await async_client.get(ENDPOINT)
        second = await async_client.get(ENDPOINT)
        third = await async_client.get(ENDPOINT)

        assert [response.status_code for response in (first, second, third)] == (
            [HTTPStatus.OK] * 3
        )
        for response in (first, second, third):
            assert len(response.json()) == WINDOW_DAYS
        # Three reads in a row can only differ if UTC midnight fell between
        # them, which legitimately shifts the window by a single day.
        assert len(set(dates_of(first.json())) & set(dates_of(third.json()))) >= (
            WINDOW_DAYS - 1
        )


class TestEmptyDataAnswersSevenZeroDays:
    """AC-004: no creations still answers 7 days, each with a count of 0.

    Scenario "The endpoint returns 7 days with zero counts when no users were
    created".
    """

    async def test_no_users_at_all_answers_seven_days_of_zeros(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """An empty database answers seven days, not an empty array."""
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK, response.text
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == WINDOW_DAYS
        assert [point["count"] for point in body] == [0] * WINDOW_DAYS

    async def test_creations_only_outside_the_window_still_answer_seven_zeros(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """History that predates the window reads as seven zero days."""
        window = await served_window(async_client)
        await seed_users_on_day(db_session, "ancient", window[0] - timedelta(days=5), 4)

        response = await async_client.get(ENDPOINT)
        assert response.status_code == HTTPStatus.OK, response.text
        assert len(response.json()) == WINDOW_DAYS
        assert sum(counts_by_day(response.json()).values()) == 0

    async def test_days_without_creations_are_present_as_zero(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """A day with no rows appears with a count of 0 rather than being absent.

        A grouped ``COUNT`` answers only the days that hold rows, so the
        zero-filling is the promise that a consumer can index seven days
        without checking whether a day existed.
        """
        window = await served_window(async_client)
        await seed_users_on_day(db_session, "one-day", window[2], 5)

        response = await async_client.get(ENDPOINT)
        counts = counts_by_day(response.json())
        assert len(counts) == WINDOW_DAYS
        assert counts[window[2]] == 5
        assert sum(counts.values()) == 5
        assert sum(count == 0 for count in counts.values()) == WINDOW_DAYS - 1

    async def test_a_deleted_creation_leaves_that_day_back_at_zero(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """A user deleted after creating is not reported as a creation."""
        window = await served_window(async_client)
        day = window[-1]
        await seed_users_on_day(db_session, "doomed", day, 2)
        doomed = await crud.get_user_by_email(db_session, email_for("doomed", 0, day))
        assert doomed is not None, "the seeded row must be readable to be deleted"
        doomed.deleted_at = at_noon(day)
        await db_session.flush()

        response = await async_client.get(ENDPOINT)
        counts = counts_by_day(response.json())
        assert len(counts) == WINDOW_DAYS
        assert counts[day] == 1, (
            "a deleted creation is not a creation the analytics reports"
        )


class TestPostIsRejected:
    """AC-005: a POST to the daily counts endpoint is rejected.

    Scenario "A POST request to the daily counts endpoint is rejected".
    """

    async def test_post_is_refused_with_method_not_allowed(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The endpoint is read-only: POST is refused, and says so plainly."""
        response = await async_client.post(ENDPOINT, json={})

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED, response.text
        assert "method" in response.text.lower()

    async def test_the_refusal_offers_get_and_not_post(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The ``Allow`` header names the method that does work here."""
        response = await async_client.post(ENDPOINT, json={})

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED, response.text
        allowed = {
            method.strip().upper()
            for method in response.headers.get("allow", "").split(",")
        }
        assert "GET" in allowed
        assert "POST" not in allowed

    async def test_posting_creates_no_user(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """A refused write writes nothing: the table is exactly as it was."""
        await seed_users_on_day(db_session, "before-post", utc_today(), 1)
        before = await crud.count_users(db_session)

        response = await async_client.post(
            ENDPOINT, json={"date": utc_today().isoformat(), "count": 99}
        )

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED, response.text
        assert await crud.count_users(db_session) == before

    async def test_a_refused_post_leaves_the_series_answerable(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Refusing the write does not disturb the read that follows it."""
        post = await async_client.post(ENDPOINT, json={})
        get = await async_client.get(ENDPOINT)

        assert post.status_code == HTTPStatus.METHOD_NOT_ALLOWED, post.text
        assert get.status_code == HTTPStatus.OK, get.text
        assert len(get.json()) == WINDOW_DAYS


class TestValidJsonResponse:
    """AC-006: the response is valid JSON.

    Scenario "The response is valid JSON" — checked as the bytes on the wire,
    their content type, and the shape they decode to.
    """

    async def test_the_body_is_json_the_standard_library_can_read(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The bytes decode as UTF-8 and parse as a JSON array."""
        response = await async_client.get(ENDPOINT)

        assert response.status_code == HTTPStatus.OK, response.text
        body = json_body(response)
        assert isinstance(body, list)
        assert len(body) == WINDOW_DAYS

    async def test_the_content_type_is_application_json(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """A consumer is told in the header what the body is."""
        response = await async_client.get(ENDPOINT)

        assert response.headers["content-type"].startswith("application/json")

    async def test_each_data_point_carries_exactly_date_and_count(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """The object keys are ``date`` and ``count`` — no more, no less."""
        window = await served_window(async_client)
        await seed_users_on_day(db_session, "keys", window[0], 1)

        response = await async_client.get(ENDPOINT)
        body = json_body(response)
        assert isinstance(body, list)
        assert body, "the array always holds the whole window"
        for point in body:
            assert isinstance(point, dict)
            assert set(point) == {"date", "count"}

    async def test_the_body_round_trips_through_the_published_schema(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """What the endpoint sends validates as ``CreatedPerDayResponse``."""
        window = await served_window(async_client)
        await seed_users_on_day(db_session, "round-trip", window[-1], 2)

        response = await async_client.get(ENDPOINT)
        parsed = CreatedPerDayResponse.model_validate(json.loads(response.content))
        assert len(parsed.root) == WINDOW_DAYS
        assert [point.count for point in parsed.root][-1] == 2

    async def test_the_error_body_is_json_too(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Even the refusal is JSON, so a caller parses one thing."""
        response = await async_client.post(ENDPOINT, json={})

        assert isinstance(json_body(response), dict)


class TestStrictDateOrdering:
    """AC-007: the data points are strictly ordered oldest to newest.

    Scenario "The data points are strictly ordered from oldest to newest",
    whose six comparisons (first<second … sixth<seventh) are checked pairwise
    here rather than one pair at a time.
    """

    async def test_each_data_point_falls_strictly_later_than_the_one_before(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """All six adjacent comparisons of the feature spec hold."""
        response = await async_client.get(ENDPOINT)
        days = dates_of(response.json())
        assert len(days) == WINDOW_DAYS

        for position, (earlier, later) in enumerate(pairwise(days)):
            assert later > earlier, (
                f"data point {position + 1} ({later.isoformat()}) is not strictly "
                f"later than data point {position} ({earlier.isoformat()})"
            )

    async def test_consecutive_data_points_are_exactly_one_day_apart(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The series is one day at a time, with no gap and no overlap."""
        response = await async_client.get(ENDPOINT)
        days = dates_of(response.json())

        assert [later - earlier for earlier, later in pairwise(days)] == [
            timedelta(days=1)
        ] * (WINDOW_DAYS - 1)

    async def test_no_day_appears_twice(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Seven data points are seven distinct days."""
        window = await served_window(async_client)
        await seed_users_on_day(db_session, "distinct", window[3], 2)

        response = await async_client.get(ENDPOINT)
        days = dates_of(response.json())
        assert len(set(days)) == len(days) == WINDOW_DAYS

    async def test_ordering_survives_uneven_counts_across_the_window(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Counts of different sizes do not reorder the days.

        A grouped query orders by day, and the series is laid over the window;
        neither should let a busy day drift out of position.
        """
        window = await served_window(async_client)
        busy, quiet = window[-2], window[1]
        await seed_users_on_day(db_session, "busy", busy, 6)
        await seed_users_on_day(db_session, "quiet", quiet, 1)

        response = await async_client.get(ENDPOINT)
        days = dates_of(response.json())
        counts = counts_by_day(response.json())

        assert days == sorted(days)
        assert days[0] < days[-1]
        assert quiet < busy
        assert counts[quiet] == 1
        assert counts[busy] == 6

    async def test_the_first_day_is_the_oldest_and_the_last_is_today(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The ends of the array are the ends of the window, in that order."""
        before = utc_today()
        response = await async_client.get(ENDPOINT)
        after = utc_today()

        assert response.status_code == HTTPStatus.OK, response.text
        days = dates_of(response.json())
        assert_window_ends_today(days, before=before, after=after)
        assert days[0] == min(days)
        assert days[-1] == max(days)


class TestLintAndFormat:
    """AC-008: the files this task touches pass the project-configured checks.

    ``ruff check`` and ``ruff format --check``, as ``pyproject.toml`` configures
    them (lint rules E, F, I, UP; double quotes, space indent).
    """

    def test_ruff_check_reports_no_errors(self) -> None:
        """`ruff check` is clean on every file this task modified."""
        result = subprocess.run(
            [*_tool("ruff"), "check", *MODIFIED_FILES],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_ruff_format_reports_no_rewrites(self) -> None:
        """`ruff format --check` would leave every file as it is."""
        result = subprocess.run(
            [*_tool("ruff"), "format", "--check", *MODIFIED_FILES],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
