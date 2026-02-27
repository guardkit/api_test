"""Base SQLAlchemy ORM model definitions."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase as SqlAlchemyDeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql.expression import text

# Type annotation for UUID primary key
UUIDPrimaryKey = Annotated[
    str,
    mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
]

# Type annotations for timestamp columns
CreatedAt = Annotated[
    datetime,
    mapped_column(
        nullable=False,
        server_default=func.now(),
    ),
]
UpdatedAt = Annotated[
    datetime,
    mapped_column(
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    ),
]


class DeclarativeBase(SqlAlchemyDeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    Provides common columns for all models:
    - id: UUID primary key
    - created_at: Timestamp of record creation
    - updated_at: Timestamp of last record update
    """

    # Re-annotate for Mypy compatibility with Mapped[T] style
    id: Mapped[UUIDPrimaryKey]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    # Recommended naming convention for Alembic migrations
    __allow_unmapped__ = True
    __mapper_args__ = {
        "naming_convention": {
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    }
