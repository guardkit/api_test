"""Users API router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_db
from src.users import crud
from src.users.exceptions import UserNotFoundError
from src.users.schemas import UserCreate, UserList, UserPublic, UserUpdate

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
