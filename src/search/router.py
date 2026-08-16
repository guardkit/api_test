"""Search API router."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.search.schemas import SearchResponse

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
        description="The search query name to look for",
        examples=["test"],
    ),
) -> SearchResponse:
    """Search endpoint.

    Accepts a `name` query parameter and returns matching results.
    """
    return SearchResponse(query=name, results=[], total=0)
