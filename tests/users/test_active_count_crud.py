"""Tests for ``crud.get_active_user_counts`` — the active/inactive split query.

Backs the data layer of GET /users/active-count (FEAT-651C). The queries run
against the real database through the ``db_session`` fixture, so the SQL —
including the conditional aggregates — is what actually executes.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate, UserUpdate


async def _make_user(db_session: AsyncSession, email: str, *, is_active: bool) -> str:
    """Create a live user and return its id with the requested active flag."""
    user = await crud.create_user(db_session, UserCreate(email=email))
    updated = await crud.update_user(
        db_session, user.id, UserUpdate(is_active=is_active)
    )
    assert updated is not None
    return updated.id


class TestActiveUserCounts:
    """AC-001/AC-002/AC-003: the shape and the split of the count query."""

    async def test_returns_both_counts_on_an_empty_database(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001 + AC-003: no users yields 0 for both keys, not None."""
        counts = await crud.get_active_user_counts(db_session)

        assert counts == {"active_count": 0, "inactive_count": 0}

    async def test_result_keys_are_the_response_field_names(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001: the mapping is keyed by active_count / inactive_count."""
        counts = await crud.get_active_user_counts(db_session)

        assert set(counts) == {"active_count", "inactive_count"}
        assert all(isinstance(value, int) for value in counts.values())

    async def test_splits_users_by_the_is_active_flag(
        self, db_session: AsyncSession
    ) -> None:
        """AC-002: each user lands in exactly one of the two counts."""
        await _make_user(db_session, "active-1@example.com", is_active=True)
        await _make_user(db_session, "active-2@example.com", is_active=True)
        await _make_user(db_session, "inactive-1@example.com", is_active=False)

        counts = await crud.get_active_user_counts(db_session)

        assert counts["active_count"] == 2
        assert counts["inactive_count"] == 1

    async def test_all_active_yields_zero_inactive(
        self, db_session: AsyncSession
    ) -> None:
        """AC-002: a flag nobody has turned off still counts as 0, not absent."""
        await _make_user(db_session, "only-active@example.com", is_active=True)

        counts = await crud.get_active_user_counts(db_session)

        assert counts == {"active_count": 1, "inactive_count": 0}

    async def test_all_inactive_yields_zero_active(
        self, db_session: AsyncSession
    ) -> None:
        """AC-002: the active count is the one that reads the flag."""
        await _make_user(db_session, "off-1@example.com", is_active=False)
        await _make_user(db_session, "off-2@example.com", is_active=False)

        counts = await crud.get_active_user_counts(db_session)

        assert counts == {"active_count": 0, "inactive_count": 2}

    async def test_flipping_the_flag_moves_the_user_between_counts(
        self, db_session: AsyncSession
    ) -> None:
        """AC-002: the counts follow the flag, not the row's age or identity."""
        user_id = await _make_user(
            db_session, "deactivating@example.com", is_active=True
        )
        assert (await crud.get_active_user_counts(db_session))["active_count"] == 1

        await crud.update_user(db_session, user_id, UserUpdate(is_active=False))
        counts = await crud.get_active_user_counts(db_session)

        assert counts == {"active_count": 0, "inactive_count": 1}

    async def test_excludes_soft_deleted_users(self, db_session: AsyncSession) -> None:
        """Deleted users are out of both counts, as in ``count_users``."""
        await _make_user(db_session, "kept@example.com", is_active=True)
        doomed = await _make_user(db_session, "doomed@example.com", is_active=True)

        assert await crud.delete_user(db_session, doomed) is True

        counts = await crud.get_active_user_counts(db_session)

        assert counts["active_count"] == await crud.count_users(db_session) == 1
        assert counts["inactive_count"] == 0

    @pytest.mark.parametrize(
        ("requested_active", "expected_active", "expected_inactive"),
        [(True, 3, 0), (False, 0, 3)],
    )
    async def test_single_state_populations(
        self,
        db_session: AsyncSession,
        requested_active: bool,
        expected_active: int,
        expected_inactive: int,
    ) -> None:
        """AC-002: one state present, the other empty, on a non-zero table."""
        for index in range(3):
            await _make_user(
                db_session,
                f"state-{requested_active}-{index}@example.com",
                is_active=requested_active,
            )

        counts = await crud.get_active_user_counts(db_session)

        assert counts == {
            "active_count": expected_active,
            "inactive_count": expected_inactive,
        }
