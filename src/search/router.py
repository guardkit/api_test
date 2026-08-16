"""Search API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_db
from src.search.schemas import SearchResponse
from src.users.models import User

router = APIRouter(tags=["search"], redirect_slashes=False)


@router.get(
    "/search",
    response_model=SearchResponse,
    tags=["search"],
    summary="Search for content",
    description=(
        "Searches for content matching the provided query name. "
        "Returns a list of matching results and the total count."
    ),
    responses={
        200: {"description": "Search completed successfully"},
    },
)
async def search(
    name: str = Query(
        default="",
        description="The search query name to look for",
        examples=["test"],
    ),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Search endpoint.

    Accepts a `name` query parameter and returns matching results.
    Uses case-insensitive substring matching on user full names.
    Empty or whitespace-only queries return all users.
    """
    if not name or not name.strip():
        stmt = select(User)
        result = await db.execute(stmt)
        users = result.scalars().all()
        results = [u.full_name for u in users if u.full_name]
        return SearchResponse(query=name, results=results, total=len(results))

    query_lower = name.lower()
    stmt = select(User)
    result = await db.execute(stmt)
    users = result.scalars().all()
    results = [
        u.full_name for u in users if u.full_name and query_lower in u.full_name.lower()
    ]
    return SearchResponse(query=name, results=results, total=len(results))
