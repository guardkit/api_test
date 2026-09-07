"""Tests for user schemas."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

import pytest
from pydantic import ValidationError

from src.users.schemas import (
    UserCreate,
    UserList,
    UserPublic,
    UserUpdate,
)


class TestUserCreate:
    """Tests for UserCreate schema."""

    def test_user_create_valid_email(self) -> None:
        """Test that valid email passes validation."""
        data = {"email": "john.doe@example.com", "full_name": "John Doe"}
        user = UserCreate(**data)

        assert user.email == "john.doe@example.com"
        assert user.full_name == "John Doe"

    def test_user_create_with_optional_full_name(self) -> None:
        """Test that full_name is optional."""
        data = {"email": "john.doe@example.com"}
        user = UserCreate(**data)

        assert user.email == "john.doe@example.com"
        assert user.full_name is None

    @pytest.mark.parametrize(
        "invalid_email",
        [
            "not-an-email",
            "missing@domain",
            "@nodomain.com",
            "no-at-sign.com",
            "",
        ],
    )
    def test_user_create_invalid_email(self, invalid_email: str) -> None:
        """Test that invalid emails raise ValidationError."""
        data = {"email": invalid_email}

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**data)

        assert "email" in str(exc_info.value)

    def test_user_create_json_schema_extra(self) -> None:
        """Test that UserCreate includes json_schema_extra with examples."""
        json_schema_extra = UserCreate.model_config.get("json_schema_extra")
        assert isinstance(json_schema_extra, Mapping)
        examples = json_schema_extra["examples"]

        assert isinstance(examples, list)
        assert len(examples) >= 1
        assert examples[0]["email"] == "john.doe@example.com"
        assert examples[0]["full_name"] == "John Doe"


class TestUserUpdate:
    """Tests for UserUpdate schema."""

    def test_user_update_valid_email(self) -> None:
        """Test that valid email passes validation."""
        data = {"email": "new.email@example.com"}
        user = UserUpdate(**data)

        assert user.email == "new.email@example.com"

    def test_user_update_with_all_fields(self) -> None:
        """Test updating all fields."""
        data = {
            "email": "updated@example.com",
            "full_name": "Updated Name",
            "is_active": False,
        }
        user = UserUpdate(**data)

        assert user.email == "updated@example.com"
        assert user.full_name == "Updated Name"
        assert user.is_active is False

    def test_user_update_with_none_fields(self) -> None:
        """Test that None values are allowed for optional fields."""
        data = {"email": None, "full_name": None, "is_active": None}
        user = UserUpdate(**data)

        assert user.email is None
        assert user.full_name is None
        assert user.is_active is None

    def test_user_update_empty(self) -> None:
        """Test that empty update is valid (all fields optional)."""
        user = UserUpdate()

        assert user.email is None
        assert user.full_name is None


class TestUserPublicDeletedAt:
    """Tests for deleted_at field in UserPublic schema."""

    def test_user_public_has_deleted_at_field(self) -> None:
        """AC-002: UserPublic schema includes deleted_at field.

        Verifies that the UserPublic schema has a deleted_at field
        that is optional (str | None).
        """
        schema = UserPublic.model_fields
        assert "deleted_at" in schema, "UserPublic must have deleted_at field"
        field_info = schema["deleted_at"]
        assert field_info.is_required() is False, "deleted_at must be optional"
        assert field_info.default is None, "deleted_at default must be None"

    def test_user_public_deleted_at_none_by_default(self) -> None:
        """Test that UserPublic accepts deleted_at=None (not soft-deleted)."""
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "john.doe@example.com",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "deleted_at": None,
        }
        user = UserPublic(**data)
        assert user.deleted_at is None

    def test_user_public_deleted_at_set(self) -> None:
        """Test that UserPublic accepts a non-None deleted_at value."""
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "john.doe@example.com",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "deleted_at": "2024-06-01T12:00:00Z",
        }
        user = UserPublic(**data)
        assert user.deleted_at == "2024-06-01T12:00:00Z"

    def test_user_public_deleted_at_datetime_formatting(self) -> None:
        """Test that UserPublic formats datetime objects for deleted_at."""
        dt = datetime(2024, 6, 1, 12, 0, 0)
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "john.doe@example.com",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "deleted_at": dt,
        }
        user = UserPublic(**data)
        assert user.deleted_at == dt.isoformat()

    def test_user_public_deleted_at_in_json_schema(self) -> None:
        """Test that deleted_at appears in the JSON schema."""
        json_schema = UserPublic.model_json_schema()
        properties = json_schema.get("properties", {})
        assert "deleted_at" in properties, "deleted_at must be in JSON schema"
        deleted_at_schema = properties["deleted_at"]
        # Pydantic may represent str | None as anyOf or type
        if "anyOf" in deleted_at_schema:
            types = {s.get("type") for s in deleted_at_schema["anyOf"]}
            assert "string" in types and "null" in types
        else:
            assert deleted_at_schema.get("type") in [
                "string",
                "null",
                ["string", "null"],
            ]

    def test_user_public_all_fields_present(self) -> None:
        """Test that UserPublic has all expected fields including deleted_at."""
        expected_fields = {
            "id",
            "email",
            "domain",
            "name",
            "full_name",
            "is_active",
            "created_at",
            "updated_at",
            "deleted_at",
        }
        actual_fields = set(UserPublic.model_fields.keys())
        assert expected_fields == actual_fields, (
            f"UserPublic must have exactly these fields: {expected_fields}"
        )


class TestUserListDeletedAt:
    """Tests for deleted_at field propagation through UserList schema."""

    def test_user_list_items_include_deleted_at(self) -> None:
        """AC-002: UserList schema includes deleted_at via UserPublic items."""
        data = {
            "items": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "john.doe@example.com",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "deleted_at": None,
                }
            ],
            "total": 1,
        }
        user_list = UserList(**data)
        assert len(user_list.items) == 1
        assert user_list.items[0].deleted_at is None

    def test_user_list_items_with_soft_deleted(self) -> None:
        """Test UserList with a soft-deleted user item."""
        data = {
            "items": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "deleted@example.com",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                    "deleted_at": "2024-06-01T12:00:00Z",
                }
            ],
            "total": 1,
        }
        user_list = UserList(**data)
        assert user_list.items[0].deleted_at == "2024-06-01T12:00:00Z"

    def test_user_update_json_schema_extra(self) -> None:
        """Test that UserUpdate includes json_schema_extra with examples."""
        json_schema_extra = UserUpdate.model_config.get("json_schema_extra")
        assert isinstance(json_schema_extra, Mapping)
        examples = json_schema_extra["examples"]

        assert isinstance(examples, list)
        assert len(examples) >= 1
        assert examples[0]["email"] == "john.doe@example.com"


class TestUserPublic:
    """Tests for UserPublic schema."""

    def test_user_public_from_attributes(self) -> None:
        """Test that UserPublic can be created from ORM model."""
        from src.users.models import User

        user = User(
            id="550e8400-e29b-41d4-a716-446655440000",
            email="john.doe@example.com",
            full_name="John Doe",
            is_active=True,
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 1, 0, 0, 0),
        )

        public_user = UserPublic.model_validate(user)

        assert public_user.id == "550e8400-e29b-41d4-a716-446655440000"
        assert public_user.email == "john.doe@example.com"
        assert public_user.full_name == "John Doe"
        assert public_user.is_active is True

    def test_user_public_with_none_full_name(self) -> None:
        """Test that full_name can be None."""
        from src.users.models import User

        user = User(
            id="550e8400-e29b-41d4-a716-446655440000",
            email="john.doe@example.com",
            full_name=None,
            is_active=True,
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 1, 0, 0, 0),
        )

        public_user = UserPublic.model_validate(user)

        assert public_user.full_name is None

    def test_user_public_json_schema_extra(self) -> None:
        """Test that UserPublic includes json_schema_extra with examples."""
        json_schema_extra = UserPublic.model_config.get("json_schema_extra")
        assert isinstance(json_schema_extra, Mapping)
        examples = json_schema_extra["examples"]

        assert isinstance(examples, list)
        assert len(examples) >= 1
        assert examples[0]["id"] == "550e8400-e29b-41d4-a716-446655440000"

    def test_user_public_datetime_serialization(self) -> None:
        """Test that datetime fields are properly serialized to strings."""
        from src.users.models import User

        user = User(
            id="550e8400-e29b-41d4-a716-446655440000",
            email="john.doe@example.com",
            full_name="John Doe",
            is_active=True,
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 30, 45),
        )

        public_user = UserPublic.model_validate(user)

        assert isinstance(public_user.created_at, str)
        assert isinstance(public_user.updated_at, str)
        assert "2024-01-01" in public_user.created_at
        assert "2024-01-02" in public_user.updated_at


class TestUserList:
    """Tests for UserList schema."""

    def test_user_list_with_items(self) -> None:
        """Test UserList with paginated results."""
        items = [
            UserPublic(
                id="1",
                email="user1@example.com",
                full_name="User 1",
                is_active=True,
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            ),
            UserPublic(
                id="2",
                email="user2@example.com",
                full_name="User 2",
                is_active=False,
                created_at="2024-01-02T00:00:00Z",
                updated_at="2024-01-02T00:00:00Z",
            ),
        ]

        user_list = UserList(items=items, total=2)

        assert len(user_list.items) == 2
        assert user_list.total == 2

    def test_user_list_empty(self) -> None:
        """Test UserList with empty results."""
        user_list = UserList(items=[], total=0)

        assert user_list.items == []
        assert user_list.total == 0

    def test_user_list_json_schema_extra(self) -> None:
        """Test that UserList includes json_schema_extra with examples."""
        json_schema_extra = UserList.model_config.get("json_schema_extra")
        assert isinstance(json_schema_extra, Mapping)
        examples = json_schema_extra["examples"]

        assert isinstance(examples, list)
        assert len(examples) >= 1
        assert "items" in examples[0]
        assert "total" in examples[0]
