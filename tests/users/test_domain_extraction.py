"""Tests for domain extraction logic."""

from __future__ import annotations

from src.users.domain_extraction import extract_domain, extract_domains


class TestExtractDomain:
    """Tests for the extract_domain function."""

    # AC-001: Correctly extracts domain from valid email addresses
    def test_simple_domain_extraction(self) -> None:
        """Valid email with simple domain should return the domain."""
        assert extract_domain("user@example.com") == "example.com"

    def test_subdomain_extraction(self) -> None:
        """Valid email with subdomain should return the full domain."""
        assert extract_domain("user@sub.domain.com") == "sub.domain.com"

    def test_hyphenated_domain(self) -> None:
        """Valid email with hyphenated domain should return the domain."""
        assert extract_domain("admin@my-domain.org") == "my-domain.org"

    def test_case_insensitive_domain(self) -> None:
        """Domain should be returned in lowercase."""
        assert extract_domain("user@EXAMPLE.COM") == "example.com"

    def test_uppercase_email(self) -> None:
        """Uppercase email should return lowercase domain."""
        assert extract_domain("USER@DOMAIN.ORG") == "domain.org"

    # AC-002: Ignores malformed email addresses
    def test_no_at_symbol(self) -> None:
        """Email without @ symbol should return None."""
        assert extract_domain("userexample.com") is None

    def test_empty_string(self) -> None:
        """Empty string should return None."""
        assert extract_domain("") is None

    def test_none_input(self) -> None:
        """None input should return None."""
        assert extract_domain(None) is None  # type: ignore[arg-type]

    def test_only_at_symbol(self) -> None:
        """String with only @ should return None."""
        assert extract_domain("@") is None

    def test_no_domain_after_at(self) -> None:
        """Email with @ but no domain should return None."""
        assert extract_domain("user@") is None

    def test_no_local_part(self) -> None:
        """Email with no local part should return None."""
        assert extract_domain("@example.com") is None

    def test_whitespace_only(self) -> None:
        """Whitespace-only string should return None."""
        assert extract_domain("   ") is None

    def test_spaces_in_email(self) -> None:
        """Email with spaces should return None."""
        assert extract_domain("user name@example.com") is None

    def test_no_dot_in_domain(self) -> None:
        """Domain without dot should return None."""
        assert extract_domain("user@localhost") is None

    def test_multiple_at_symbols(self) -> None:
        """Email with multiple @ symbols should return None."""
        assert extract_domain("user@name@example.com") is None

    # AC-003: Handles edge cases
    def test_single_char_domain(self) -> None:
        """Domain with single character before TLD should return None."""
        assert extract_domain("user@a.b") is None

    def test_long_tld(self) -> None:
        """Email with long TLD should extract domain."""
        assert extract_domain("user@example.museum") == "example.museum"

    def test_numeric_domain(self) -> None:
        """Email with numeric domain should extract domain."""
        assert extract_domain("user@123.com") == "123.com"

    def test_deep_subdomain(self) -> None:
        """Email with deep subdomain should extract full domain."""
        assert extract_domain("user@a.b.c.example.com") == "a.b.c.example.com"

    def test_special_chars_in_local_part(self) -> None:
        """Special characters in local part (before @) are acceptable."""
        assert extract_domain("user.name+tag@example.com") == "example.com"

    def test_empty_email_list(self) -> None:
        """Empty list should return empty list."""
        assert extract_domains([]) == []


class TestExtractDomains:
    """Tests for the extract_domains function (batch extraction)."""

    # AC-001: Extracts domains from valid emails
    def test_multiple_valid_emails(self) -> None:
        """Multiple valid emails should return corresponding domains."""
        emails = ["user@example.com", "admin@domain.org"]
        result = extract_domains(emails)
        assert len(result) == 2
        assert result[0] == "example.com"
        assert result[1] == "domain.org"

    def test_mixed_valid_and_invalid(self) -> None:
        """Invalid emails should be skipped, only valid domains returned."""
        emails = ["user@example.com", "invalid", "admin@domain.org"]
        result = extract_domains(emails)
        assert len(result) == 2
        assert result[0] == "example.com"
        assert result[1] == "domain.org"

    def test_all_invalid(self) -> None:
        """All invalid emails should return empty list."""
        emails = ["invalid", "no-at-sign", "@no-local.com"]
        result = extract_domains(emails)
        assert result == []

    def test_case_insensitive_batch(self) -> None:
        """All domains should be lowercased in batch extraction."""
        emails = ["User@EXAMPLE.COM", "Admin@DOMAIN.ORG"]
        result = extract_domains(emails)
        assert result == ["example.com", "domain.org"]

    def test_duplicate_domains(self) -> None:
        """Duplicate domains should be preserved in output."""
        emails = ["user1@example.com", "user2@example.com"]
        result = extract_domains(emails)
        assert len(result) == 2
        assert result[0] == "example.com"
        assert result[1] == "example.com"
