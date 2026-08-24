"""Tests for users module validation utilities."""

from __future__ import annotations

from http import HTTPStatus

import pytest

from src.users.validators import validate_user_id


class TestValidateUserId:
    """Tests for validate_user_id function."""

    # AC-001: Validate that ID segment is non-empty (per ASSUM-003)

    def test_valid_uuid_returns_id(self) -> None:
        """Valid UUID string should be returned unchanged."""
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = validate_user_id(valid_uuid)
        assert result == valid_uuid

    def test_valid_uuid_with_hyphens_returns_id(self) -> None:
        """Valid UUID with standard hyphenated format should be accepted."""
        valid_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = validate_user_id(valid_uuid)
        assert result == valid_uuid

    def test_empty_string_raises_value_error(self) -> None:
        """Empty string ID should raise ValueError (AC-001)."""
        with pytest.raises(ValueError, match="must not be empty"):
            validate_user_id("")

    def test_whitespace_only_raises_value_error(self) -> None:
        """Whitespace-only string ID should raise ValueError (AC-001)."""
        with pytest.raises(ValueError, match="must not be empty"):
            validate_user_id("   ")

    def test_none_raises_value_error(self) -> None:
        """None ID should raise ValueError (AC-001)."""
        with pytest.raises(ValueError, match="must not be empty"):
            validate_user_id(None)  # type: ignore[arg-type]

    def test_spaces_only_raises_value_error(self) -> None:
        """String of spaces should raise ValueError (AC-001)."""
        with pytest.raises(ValueError, match="must not be empty"):
            validate_user_id("  ")

    # AC-002: Reject IDs with invalid special characters

    def test_special_chars_at_sign_rejected(self) -> None:
        """ID with @ character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user@id")

    def test_special_chars_hash_rejected(self) -> None:
        """ID with # character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user#id")

    def test_special_chars_dollar_rejected(self) -> None:
        """ID with $ character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user$id")

    def test_special_chars_ampersand_rejected(self) -> None:
        """ID with & character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user&id")

    def test_special_chars_asterisk_rejected(self) -> None:
        """ID with * character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user*id")

    def test_special_chars_slash_rejected(self) -> None:
        """ID with / character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user/id")

    def test_special_chars_backslash_rejected(self) -> None:
        """ID with \\ character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user\\id")

    def test_special_chars_pipe_rejected(self) -> None:
        """ID with | character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user|id")

    def test_special_chars_semicolon_rejected(self) -> None:
        """ID with ; character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user;id")

    def test_special_chars_colon_rejected(self) -> None:
        """ID with : character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user:id")

    def test_special_chars_quotes_rejected(self) -> None:
        """ID with double quotes should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id('user"id')

    def test_special_chars_newline_rejected(self) -> None:
        """ID with newline should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user\nid")

    def test_special_chars_tab_rejected(self) -> None:
        """ID with tab should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user\tid")

    def test_special_chars_brackets_rejected(self) -> None:
        """ID with brackets should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user[id")

    def test_special_chars_parentheses_rejected(self) -> None:
        """ID with parentheses should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user(id")

    def test_special_chars_curly_braces_rejected(self) -> None:
        """ID with curly braces should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user{id")

    def test_special_chars_angle_brackets_rejected(self) -> None:
        """ID with angle brackets should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user<id")

    def test_special_chars_comma_rejected(self) -> None:
        """ID with comma should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user,id")

    def test_special_chars_question_mark_rejected(self) -> None:
        """ID with ? character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user?id")

    def test_special_chars_plus_rejected(self) -> None:
        """ID with + character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user+id")

    def test_special_chars_equals_rejected(self) -> None:
        """ID with = character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user=id")

    def test_special_chars_dot_rejected(self) -> None:
        """ID with . character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user.id")

    def test_special_chars_tilde_rejected(self) -> None:
        """ID with ~ character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user~id")

    def test_special_chars_caret_rejected(self) -> None:
        """ID with ^ character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user^id")

    def test_special_chars_exclamation_rejected(self) -> None:
        """ID with ! character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user!id")

    def test_special_chars_percent_rejected(self) -> None:
        """ID with % character should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user%id")

    def test_special_chars_space_rejected(self) -> None:
        """ID with space should be rejected (AC-002)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_user_id("user id")

    # Valid characters should be accepted

    def test_alphanumeric_uuid_accepted(self) -> None:
        """Alphanumeric UUID with hyphens should be accepted."""
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = validate_user_id(valid_uuid)
        assert result == valid_uuid

    def test_valid_uuid_lowercase_accepted(self) -> None:
        """Valid lowercase UUID should be accepted."""
        result = validate_user_id("550e8400e29b41d4a716446655440000")
        assert result == "550e8400e29b41d4a716446655440000"

    def test_valid_uuid_mixed_case_accepted(self) -> None:
        """Valid UUID with mixed case should be accepted."""
        result = validate_user_id("550E8400-e29b-41D4-a716-446655440000")
        assert result == "550E8400-e29b-41D4-a716-446655440000"

    # UUID format validation

    def test_invalid_uuid_format_raises_value_error(self) -> None:
        """Non-UUID format should raise ValueError even if characters are valid."""
        # Valid characters but not a UUID
        with pytest.raises(ValueError, match="must be a valid UUID"):
            validate_user_id("not-a-uuid")

    def test_uuid_with_extra_chars_raises_value_error(self) -> None:
        """UUID with extra characters should raise ValueError."""
        with pytest.raises(ValueError, match="must be a valid UUID"):
            validate_user_id("550e8400-e29b-41d4-a716-4466554400000")
