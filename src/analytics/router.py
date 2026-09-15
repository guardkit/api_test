"""Analytics API router: the daily user-creation counts (TASK-6F3D-003).

This is the HTTP face of ``src.analytics.crud.get_users_created_per_day``:
``GET /users/created-per-day`` answers the last seven calendar days of user
creations, oldest first, as a bare JSON array of ``{date, count}`` objects
(FEAT-6F3D, ASSUM-001).

Two things about the address are worth recording, because neither is obvious
from the file it lives in:

* **The URL belongs to the users namespace, the code does not.** The feature
  spec names the endpoint ``GET /users/created-per-day``, so this router
  declares ``prefix="/users"`` while living in ``src/analytics/``: ADR-001
  puts a feature's router with its feature, not with the URL it serves, and
  analytics owns no table to hang the route on.
* **It has to be registered before the users router.** ``src/users/router.py``
  serves ``GET /users/{user_id}``, and FastAPI answers a request with the
  first route that matches, so registering later would have the literal path
  "created-per-day" read as a user id and rejected by that endpoint's
  validation. ``src/main.py`` includes this router first for that reason.

The handler counts nothing of its own. The window and the day-grouping are the
query layer's business, and ``CreatedPerDayResponse`` is the contract the
response is checked against on the way out, so a reply that drifted from the
schema — a missing day, a negative count, an unordered series — cannot leave
the process.

The database session comes from ``src.db``, which the architecture record
lists as an infrastructure module (docs/architecture-rules.yaml, ``layout``)
rather than a feature, so reaching it through the package's public ``get_db``
keeps analytics clear of every other feature's private files.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.analytics.crud import get_users_created_per_day
from src.analytics.schemas import CreatedPerDayResponse
from src.db import get_db

logger = logging.getLogger(__name__)

#: The URL namespace this endpoint answers under. See the module docstring for
#: why analytics serves a path in the users namespace.
ROUTER_PREFIX = "/users"

#: The path below the prefix, named so tests and docs can refer to one thing.
CREATED_PER_DAY_PATH = "/created-per-day"

router = APIRouter(prefix=ROUTER_PREFIX, redirect_slashes=False)


@router.get(
    CREATED_PER_DAY_PATH,
    response_model=CreatedPerDayResponse,
    tags=["analytics"],
    summary="Get daily user creation counts",
    description=(
        "Returns the number of users created on each of the last 7 calendar "
        "days (UTC), oldest first, as a JSON array of objects with an "
        "ISO-8601 `date` and a non-negative integer `count`. Days with no "
        "creations are present with a count of 0, so the array always holds "
        "exactly 7 data points."
    ),
    responses={
        503: {"description": "Database unavailable"},
    },
)
async def get_created_per_day(
    db: AsyncSession = Depends(get_db),
) -> CreatedPerDayResponse:
    """Serve the last seven days of user-creation counts, oldest first.

    Args:
        db: The async database session, injected by FastAPI.

    Returns:
        CreatedPerDayResponse: Exactly seven data points, one per calendar day
        of the window ending today (UTC), each a non-negative count. Days with
        no creations carry a count of zero rather than being absent.

    Raises:
        HTTPException: 503 when the database refuses or fails the query, so a
            caller can retry instead of receiving a short or partial series.
            The underlying error is chained and logged, never swallowed.
    """
    try:
        return await get_users_created_per_day(db)
    except SQLAlchemyError as exc:
        logger.error(
            "GET %s%s failed: %s: %s",
            ROUTER_PREFIX,
            CREATED_PER_DAY_PATH,
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {exc}",
        ) from exc


__all__ = ["CREATED_PER_DAY_PATH", "ROUTER_PREFIX", "get_created_per_day", "router"]
