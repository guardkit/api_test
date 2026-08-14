"""Tests for version utility functions."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from src.version.utils import get_git_commit_hash


def test_get_git_commit_hash_returns_7_characters() -> None:
    """Test that get_git_commit_hash returns a 7-character string."""
    commit_hash = get_git_commit_hash()

    # Should return either "unknown" or a 7-character hex string
    assert isinstance(commit_hash, str)
    if commit_hash != "unknown":
        assert len(commit_hash) == 7
        assert all(c in "0123456789abcdef" for c in commit_hash.lower())


def test_get_git_commit_hash_returns_unknown_when_git_fails() -> None:
    """Test that get_git_commit_hash returns 'unknown' when git command fails."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=128, cmd=["git", "rev-parse", "--short=7", "HEAD"]
        )

        result = get_git_commit_hash()

        assert result == "unknown"


def test_get_git_commit_hash_returns_unknown_when_git_not_found() -> None:
    """Test that get_git_commit_hash returns 'unknown' when git is not installed."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()

        result = get_git_commit_hash()

        assert result == "unknown"


def test_get_git_commit_hash_returns_unknown_when_git_timeout() -> None:
    """Test that get_git_commit_hash returns 'unknown' when git command times out."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["git", "rev-parse", "--short=7", "HEAD"],
            timeout=5,
        )

        result = get_git_commit_hash()

        assert result == "unknown"


def test_get_git_commit_hash_returns_unknown_when_no_git_directory() -> None:
    """Test that get_git_commit_hash returns 'unknown' when not in a git repository."""
    with patch("pathlib.Path.exists") as mock_exists:
        # Simulate no .git directory found
        mock_exists.return_value = False

        result = get_git_commit_hash()

        assert result == "unknown"


def test_get_git_commit_hash_uses_correct_git_command() -> None:
    """Test that get_git_commit_hash uses the correct git command."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "abc1234\n"
        mock_run.return_value = mock_result

        get_git_commit_hash()

        # Verify git command was called with correct arguments
        assert mock_run.called
        call_args = mock_run.call_args
        assert call_args[0][0] == ["git", "rev-parse", "--short=7", "HEAD"]
        assert call_args[1]["capture_output"] is True
        assert call_args[1]["text"] is True
        assert call_args[1]["check"] is True
        assert call_args[1]["timeout"] == 5


def test_get_git_commit_hash_strips_whitespace() -> None:
    """Test that get_git_commit_hash strips whitespace from git output."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "  abc1234  \n\n"
        mock_run.return_value = mock_result

        result = get_git_commit_hash()

        assert result == "abc1234"
        assert result == result.strip()
