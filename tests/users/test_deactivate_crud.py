"""Tests for the deactivation logic in the CRUD layer (TASK-2FDE-002, FEAT-2FDE).

The route's HTTP contract is pinned in ``tests/users/test_deactivate_user.py``.
These cover the layer underneath it: what ``crud.deactivate_user`` does to the
row, what it raises when there is nothing to act on, and what two callers
racing for the same user get.

The cases that have to prove a write landed read back through a second session
on the same engine, the way ``TestTheWritesOutliveTheirSession`` does. The
session dependency never commits, so a write that was never written down still
reads back inside the session that made it.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.users import crud
from src.users.exceptions import UserAlreadyInactiveError, UserNotFoundError
from src.users.schemas import UserCreate, UserUpdate


async def _make_user(db: AsyncSession, email: str, *, is_active: bool = True) -> str:
    """Create a live user through the application's own CRUD layer."""
    user = await crud.create_user(db, UserCreate(email=email))
    if not is_active:
        updated = await crud.update_user(db, str(user.id), UserUpdate(is_active=False))
        assert updated is not None
    return str(user.id)


class TestDeactivationUpdatesTheUser:
    """AC-001: the deactivation flips the status and returns that user."""

    async def test_returns_the_user_with_the_status_flipped(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001: an active user comes back inactive from the CRUD layer."""
        user_id = await _make_user(db_session, "crud-off@example.com")

        user = await crud.deactivate_user(db_session, user_id)

        assert user.id == user_id
        assert user.is_active is False

    async def test_only_the_status_changes(self, db_session: AsyncSession) -> None:
        """AC-001: deactivating is a status change, not a rewrite of the user."""
        user_id = await _make_user(db_session, "keep-me@example.com")

        user = await crud.deactivate_user(db_session, user_id)

        assert user.email == "keep-me@example.com"
        assert user.domain == "example.com"
        assert user.deleted_at is None

    async def test_the_deactivation_is_written_down(
        self, db_engine: AsyncEngine
    ) -> None:
        """AC-001: the next session sees the row inactive, not just this one.

        The session dependency does not commit, so this is the only place in
        these tests that can tell a write from an intention to write.
        """
        maker = async_sessionmaker(bind=db_engine, expire_on_commit=False)
        async with maker() as writing:
            user_id = await _make_user(writing, "written-down@example.com")
            await crud.deactivate_user(writing, user_id)

        async with maker() as reading:
            found = await crud.get_user(reading, user_id)

        assert found is not None, (
            "the deactivation was not written down: the next request would "
            "still report the user as active"
        )
        assert found.is_active is False


class TestDeactivationWithNoSuchUser:
    """AC-002: there is no live user to deactivate."""

    async def test_unknown_id_raises_not_found(self, db_session: AsyncSession) -> None:
        """AC-002: an id nobody holds is a missing user, not a silent no-op."""
        with pytest.raises(UserNotFoundError):
            await crud.deactivate_user(
                db_session, "00000000-0000-4000-8000-000000000000"
            )

    async def test_soft_deleted_user_raises_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """AC-002: a soft-deleted row is not a user this operation may act on."""
        user_id = await _make_user(db_session, "crud-gone@example.com")
        assert await crud.delete_user(db_session, user_id) is True

        with pytest.raises(UserNotFoundError):
            await crud.deactivate_user(db_session, user_id)

    async def test_nothing_is_written_for_a_missing_user(
        self, db_engine: AsyncEngine
    ) -> None:
        """AC-002: the rejected call leaves the table as it found it."""
        maker = async_sessionmaker(bind=db_engine, expire_on_commit=False)
        async with maker() as writing:
            user_id = await _make_user(writing, "untouched-crud@example.com")

        async with maker() as failing:
            with pytest.raises(UserNotFoundError):
                await crud.deactivate_user(failing, "no-such-user")

        async with maker() as reading:
            found = await crud.get_user(reading, user_id)

        assert found is not None
        assert found.is_active is True


class TestDeactivationOfAnAlreadyInactiveUser:
    """AC-003: the user is already inactive."""

    async def test_inactive_user_raises_conflict(
        self, db_session: AsyncSession
    ) -> None:
        """AC-003: a second deactivation conflicts rather than repeating."""
        user_id = await _make_user(
            db_session, "crud-already-off@example.com", is_active=False
        )

        with pytest.raises(UserAlreadyInactiveError):
            await crud.deactivate_user(db_session, user_id)

    async def test_the_conflict_names_the_user(self, db_session: AsyncSession) -> None:
        """AC-003: the conflict carries the id, so the route can report it."""
        user_id = await _make_user(
            db_session, "crud-named-off@example.com", is_active=False
        )

        with pytest.raises(UserAlreadyInactiveError) as exc_info:
            await crud.deactivate_user(db_session, user_id)

        assert user_id in str(exc_info.value.detail)

    async def test_the_conflict_writes_nothing(self, db_engine: AsyncEngine) -> None:
        """AC-003: the rejected call leaves the row exactly as it found it."""
        maker = async_sessionmaker(bind=db_engine, expire_on_commit=False)
        async with maker() as writing:
            user_id = await _make_user(writing, "conflict-quiet@example.com")
            await crud.deactivate_user(writing, user_id)

        async with maker() as second:
            with pytest.raises(UserAlreadyInactiveError):
                await crud.deactivate_user(second, user_id)

        async with maker() as reading:
            found = await crud.get_user(reading, user_id)

        assert found is not None
        assert found.is_active is False


class TestDeactivationIsAtomic:
    """AC-004: the check and the write are one step, not two."""

    async def test_a_caller_that_lost_the_race_reports_conflict(
        self, db_engine: AsyncEngine
    ) -> None:
        """AC-004: the decision comes from the write, not from an earlier read.

        This caller has the row loaded and believes it is active. Another
        writer deactivates it in the meantime, so the claim must fail on the
        database's state and say conflict — a read-then-write would say 200
        twice and lose one answer.
        """
        maker = async_sessionmaker(bind=db_engine, expire_on_commit=False)
        async with maker() as writing:
            user_id = await _make_user(writing, "lost-the-race@example.com")

        async with maker() as loser, maker() as winner:
            stale = await crud.get_user(loser, user_id)
            assert stale is not None and stale.is_active is True

            await crud.deactivate_user(winner, user_id)

            with pytest.raises(UserAlreadyInactiveError):
                await crud.deactivate_user(loser, user_id)

    async def test_two_racing_callers_split_the_answer(
        self, db_engine: AsyncEngine
    ) -> None:
        """AC-004: of two simultaneous deactivations, one deactivates.

        The other is told the user was already inactive, and the row ends
        inactive either way — so the flag cannot be written twice by two
        callers who both saw it active.
        """
        maker = async_sessionmaker(bind=db_engine, expire_on_commit=False)
        async with maker() as writing:
            user_id = await _make_user(writing, "both-at-once@example.com")

        async def attempt() -> str:
            async with maker() as session:
                try:
                    await crud.deactivate_user(session, user_id)
                except UserAlreadyInactiveError:
                    return "conflict"
                return "deactivated"

        results = await asyncio.gather(attempt(), attempt())

        assert sorted(results) == ["conflict", "deactivated"]

        async with maker() as reading:
            found = await crud.get_user(reading, user_id)
        assert found is not None
        assert found.is_active is False
