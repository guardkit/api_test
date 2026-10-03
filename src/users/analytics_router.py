"""HTTP surface for the user creation analytics query.

Exposes ``GET /users/created-per-day``: the number of users created on each of
the last seven calendar days — today and the six days before it — oldest first,
with soft-deleted users counted alongside live ones. The query itself lives in
src/users/analytics_crud.py and the response shape in
src/users/analytics_schemas.py; this module only moves one into the other.

The router carries the ``/users`` prefix so the complete path is
/users/created-per-day. It must be registered ahead of the main users router in
src/main.py: that router declares ``GET /users/{user_id}`` and FastAPI answers
the first route that matches, so registering later would have this literal path
swallowed by the ID route and refused as a malformed UUID.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_db
from src.users import analytics_crud
from src.users.analytics_schemas import UserCreatedPerDayResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", redirect_slashes=False)


@router.get(
    "/created-per-day",
    response_model=UserCreatedPerDayResponse,
    tags=["users"],
    summary="Get user creation counts per day",
    description=(
        "Returns the number of users created on each of the last 7 calendar "
        "days — today and the six days before it — oldest first, as a JSON "
        "array of {date, count} objects. Days with no new users are present "
        "with a count of 0. Soft-deleted users are counted along with active "
        "ones. Takes no parameters."
    ),
    responses={
        503: {"description": "Database unavailable"},
    },
)
async def get_users_created_per_day(
    db: AsyncSession = Depends(get_db),
) -> UserCreatedPerDayResponse:
    """Get the number of users created on each of the last 7 days.

    Returns a JSON array of 7 {date, count} objects, oldest day first.
    Returns 503 if the database is unavailable.
    """
    try:
        rows = await analytics_crud.get_created_per_day(db)
    except SQLAlchemyError as exc:
        logger.error(
            "Database error while counting users created per day: %s",
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {exc}",
        ) from exc
    return UserCreatedPerDayResponse.model_validate(rows)
