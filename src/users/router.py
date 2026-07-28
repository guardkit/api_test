"""Users API router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_db
from src.users import crud
from src.users.exceptions import UserNotFoundError
from pydantic import EmailStr

from src.users.schemas import UserCountResponse, UserCreate, UserList, UserPublic, UserUpdate

router = APIRouter(prefix="/users", redirect_slashes=False)


@router.post(
    "",
    response_model=UserPublic,
    status_code=201,
    tags=["users"],
    summary="Create a new user",
    description="Creates a new user with the provided email and optional full name.",
    responses={
        201: {"description": "User created successfully"},
        409: {"description": "User with this email already exists"},
    },
)
async def create_user(
    user_in: UserCreate, db: AsyncSession = Depends(get_db)
) -> UserPublic:
    """Create a new user."""
    user = await crud.create_user(db, user_in)
    return UserPublic.model_validate(user)


@router.get(
    "",
    response_model=UserList,
    tags=["users"],
    summary="List users with pagination",
    description="Returns a paginated list of users.",
)
async def list_users(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
) -> UserList:
    """List users with optional pagination."""
    users = await crud.get_users(db, skip=skip, limit=limit)
    total = await crud.count_users(db)
    return UserList(items=[UserPublic.model_validate(u) for u in users], total=total)


@router.get(
    "/count",
    response_model=UserCountResponse,
    tags=["users"],
    summary="Get total user count",
    description="Returns the total number of users stored in the database.",
    responses={
        503: {"description": "Database unavailable"},
    },
)
async def get_user_count(db: AsyncSession = Depends(get_db)) -> UserCountResponse:
    """Get total user count.

    Returns the total number of users in the database.
    Returns 503 if the database is unavailable.
    """
    try:
        total = await crud.count_users(db)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {exc}",
        ) from exc
    return UserCountResponse(count=total)


@router.get(
    "/by-email",
    response_model=UserPublic,
    tags=["users"],
    summary="Get user by email",
    description="Retrieves a user by their exact email address.",
    responses={
        404: {"description": "User not found"},
        503: {"description": "Database unavailable"},
    },
)
async def get_user_by_email(
    email: EmailStr, db: AsyncSession = Depends(get_db)
) -> UserPublic:
    """Get user by email.

    Returns the user with the exact matching email address.
    Returns 404 if no user has that email.
    Returns 503 if the database is unavailable.
    """
    try:
        user = await crud.get_user_by_email(db, email)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {exc}",
        ) from exc
    if user is None:
        raise HTTPException(
            status_code=404,
            detail=f"User with email '{email}' not found",
        )
    return UserPublic.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserPublic,
    tags=["users"],
    summary="Get user by ID",
    description="Retrieves a specific user by their UUID.",
    responses={
        404: {"description": "User not found"},
    },
)
async def get_user(user_id: UUID, db: AsyncSession = Depends(get_db)) -> UserPublic:
    """Get user by ID."""
    user = await crud.get_user(db, str(user_id))
    if user is None:
        raise UserNotFoundError(user_id=str(user_id))
    return UserPublic.model_validate(user)


@router.put(
    "/{user_id}",
    response_model=UserPublic,
    tags=["users"],
    summary="Update user",
    description="Updates an existing user with the provided data.",
    responses={
        404: {"description": "User not found"},
    },
)
async def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
) -> UserPublic:
    """Update user."""
    user = await crud.update_user(db, str(user_id), user_in)
    if user is None:
        raise UserNotFoundError(user_id=str(user_id))
    return UserPublic.model_validate(user)


@router.delete(
    "/by-email",
    status_code=204,
    tags=["users"],
    summary="Delete user by email",
    description="Deletes a user by their exact email address. Returns 204 No Content on success.",
    responses={
        204: {"description": "User deleted successfully"},
        404: {"description": "User not found"},
        422: {"description": "Malformed email address"},
        503: {"description": "Database unavailable"},
    },
)
async def delete_user_by_email(
    email: EmailStr, db: AsyncSession = Depends(get_db)
) -> Response:
    """Delete user by email.

    Finds the user with the exact matching email address and deletes them.
    Returns 204 on success, 404 if no user has that email, 503 if the database is unavailable.
    """
    try:
        user = await crud.get_user_by_email(db, email)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {exc}",
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=404,
            detail=f"User with email '{email}' not found",
        )

    try:
        deleted = await crud.delete_user(db, str(user.id))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {exc}",
        ) from exc

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"User with email '{email}' not found",
        )
    return Response(status_code=204)


@router.delete(
    "/{user_id}",
    status_code=204,
    tags=["users"],
    summary="Delete user",
    description="Deletes a user by ID. Returns 204 No Content on success.",
    responses={
        204: {"description": "User deleted successfully"},
        404: {"description": "User not found"},
    },
)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete user."""
    deleted = await crud.delete_user(db, str(user_id))
    if not deleted:
        raise UserNotFoundError(user_id=str(user_id))
    return Response(status_code=204)
