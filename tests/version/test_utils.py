"""Tests for version utility functions."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from src.version.utils import get_git_commit_hash


def test_get_git_commit_hash_returns_40_characters() -> None:
    """Test that get_git_commit_hash returns a 40-character string."""
    commit_hash = get_git_commit_hash()

    # Should return either "unknown" or a 40-character hex string
    assert isinstance(commit_hash, str)
    if commit_hash != "unknown":
        assert len(commit_hash) == 40
        assert all(c in "0123456789abcdef" for c in commit_hash.lower())


def test_get_git_commit_hash_returns_unknown_when_git_fails() -> None:
    """Test that get_git_commit_hash returns 'unknown' when git command fails."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=128, cmd=["git", "rev-parse", "HEAD"]
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
            cmd=["git", "rev-parse", "HEAD"],
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
        mock_result.stdout = "1b0f90ba3c7e5d6a9f2b1c4d8e0f3a5b7c9d1e2f\n"
        mock_run.return_value = mock_result

        get_git_commit_hash()

        # Verify git command was called with correct arguments
        assert mock_run.called
        call_args = mock_run.call_args
        assert call_args[0][0] == ["git", "rev-parse", "HEAD"]
        assert call_args[1]["capture_output"] is True
        assert call_args[1]["text"] is True
        assert call_args[1]["check"] is True
        assert call_args[1]["timeout"] == 5


def test_get_git_commit_hash_strips_whitespace() -> None:
    """Test that get_git_commit_hash strips whitespace from git output."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "  1b0f90ba3c7e5d6a9f2b1c4d8e0f3a5b7c9d1e2f  \n\n"
        mock_run.return_value = mock_result

        result = get_git_commit_hash()

        assert result == "1b0f90ba3c7e5d6a9f2b1c4d8e0f3a5b7c9d1e2f"
        assert result == result.strip()
