"""
Tests for file_operations.py
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from evoseal.utils.version_control.file_operations import (
    FileInfo,
    FileOperations,
    FileStatus,
)


class TestFileOperations:
    """Test cases for FileOperations class."""

    @pytest.fixture
    def mock_git(self):
        """Create a mock Git interface."""
        mock = MagicMock()
        mock._run_git_command.return_value = (0, "", "")  # (returncode, stdout, stderr)
        return mock

    @pytest.fixture
    def file_ops(self, mock_git):
        """Create a FileOperations instance with a mock Git interface."""
        return FileOperations(mock_git)

    def test_stage_files(self, file_ops, mock_git):
        """Test staging files."""
        # Test with single file
        file_ops.stage_files("test.txt")
        mock_git._run_git_command.assert_called_with(["add", "--", "test.txt"])

        # Test with multiple files
        mock_git.reset_mock()
        file_ops.stage_files("file1.txt", "file2.txt")
        mock_git._run_git_command.assert_called_with(
            ["add", "--", "file1.txt", "file2.txt"]
        )

    def test_unstage_files(self, file_ops, mock_git):
        """Test unstaging files."""
        # Test with single file
        file_ops.unstage_files("test.txt")
        mock_git._run_git_command.assert_called_with(
            ["restore", "--staged", "--", "test.txt"]
        )

        # Test with multiple files
        mock_git.reset_mock()
        file_ops.unstage_files("file1.txt", "file2.txt")
        mock_git._run_git_command.assert_called_with(
            ["restore", "--staged", "--", "file1.txt", "file2.txt"]
        )

    def test_get_file_status(self, file_ops, mock_git):
        """Test getting status of a specific file."""
        # Mock the get_status method
        expected_status = FileInfo(
            path=Path("test.txt"), status=FileStatus.MODIFIED, staged=True
        )
        with patch.object(
            file_ops, "get_status", return_value={Path("test.txt"): expected_status}
        ):
            status = file_ops.get_file_status("test.txt")
            assert status == expected_status

    def test_parse_status_output(self, file_ops):
        """Test parsing git status output."""
        # Test with a modified file
        status_output = (
            "1 M. N... 100644 100644 100644 1234567 1234567 1234567 test.txt"
        )
        result = file_ops._parse_status_output(status_output)
        assert Path("test.txt") in result
        assert result[Path("test.txt")].status == FileStatus.MODIFIED
        assert result[Path("test.txt")].staged is True

        # Test with a renamed file
        status_output = (
            "1 R. N... 100644 100644 100644 1234567 1234567 1234567 old.txt new.txt"
        )
        result = file_ops._parse_status_output(status_output)
        assert Path("new.txt") in result
        assert result[Path("new.txt")].status == FileStatus.RENAMED
        assert result[Path("new.txt")].staged is True
        assert result[Path("new.txt")].original_path == Path("old.txt")

        # Test with a copied file
        status_output = (
            "1 C. N... 100644 100644 100644 1234567 1234567 1234567 source.txt dest.txt"
        )
        result = file_ops._parse_status_output(status_output)
        assert Path("dest.txt") in result
        assert result[Path("dest.txt")].status == FileStatus.COPIED
        assert result[Path("dest.txt")].staged is True
        assert result[Path("dest.txt")].original_path == Path("source.txt")

        # Test with an untracked file
        status_output = "? untracked.txt"
        result = file_ops._parse_status_output(status_output)
        assert Path("untracked.txt") in result
        assert result[Path("untracked.txt")].status == FileStatus.UNTRACKED
        assert result[Path("untracked.txt")].staged is False

        # Test with an untracked file
        status_output = "?? untracked.txt"
        result = file_ops._parse_status_output(status_output)
        assert Path("untracked.txt") in result
        assert result[Path("untracked.txt")].status == FileStatus.UNTRACKED
        assert result[Path("untracked.txt")].staged is False

    def test_parse_status_xy(self, file_ops):
        """Test parsing XY status codes."""
        # Test various status codes
        assert file_ops._parse_status_xy("M ") == FileStatus.MODIFIED
        assert file_ops._parse_status_xy(" M") == FileStatus.MODIFIED
        assert file_ops._parse_status_xy("A ") == FileStatus.STAGED
        assert file_ops._parse_status_xy("D ") == FileStatus.DELETED
        assert file_ops._parse_status_xy("R ") == FileStatus.RENAMED
        assert file_ops._parse_status_xy("C ") == FileStatus.COPIED
        assert file_ops._parse_status_xy("UU") == FileStatus.UPDATED_BUT_UNMERGED

    def test_get_file_diff(self, file_ops, mock_git):
        """Test getting file diff."""
        # Test with unstaged diff
        file_ops.get_file_diff("test.txt")
        mock_git._run_git_command.assert_called_with(
            ["diff", "--no-ext-diff", "--", "test.txt"]
        )

        # Test with staged diff
        mock_git.reset_mock()
        file_ops.get_file_diff("test.txt", staged=True)
        mock_git._run_git_command.assert_called_with(
            ["diff", "--staged", "--no-ext-diff", "--", "test.txt"]
        )

    def test_get_file_history(self, file_ops, mock_git):
        """Test getting file history."""
        # Mock the git log output
        mock_git._run_git_command.return_value = (
            0,
            "1234567|||Commit message|||Author Name|||2023-01-01 12:00:00 +0000\n"
            "7654321|||Another commit|||Another Author|||2023-01-02 12:00:00 +0000",
            "",
        )

        history = file_ops.get_file_history("test.txt", limit=2)
        assert len(history) == 2
        assert history[0]["hash"] == "1234567"
        assert history[0]["subject"] == "Commit message"
        assert history[1]["hash"] == "7654321"
        assert history[1]["author"] == "Another Author"

    def test_is_binary_file(self, file_ops, mock_git):
        """Test binary file detection."""
        # Test with binary file
        mock_git._run_git_command.return_value = (0, "-\t-\tbinary.bin", "")
        assert file_ops.is_binary_file("binary.bin") is True

        # Test with text file
        mock_git._run_git_command.return_value = (0, "1\t2\ttext.txt", "")
        assert file_ops.is_binary_file("text.txt") is False

    def test_get_conflicted_files(self, file_ops, mock_git):
        """Test getting conflicted files."""
        # Mock the git diff output
        mock_git._run_git_command.return_value = (0, "file1.txt\nfile2.txt\n", "")

        conflicted = file_ops.get_conflicted_files()
        assert len(conflicted) == 2
        assert Path("file1.txt") in conflicted
        assert Path("file2.txt") in conflicted

    def test_resolve_conflict(self, file_ops, mock_git, tmp_path):
        """Test resolving a conflict."""
        # Create a temporary file
        file_path = tmp_path / "conflict.txt"
        file_path.write_text("resolved content")

        # Test successful resolution
        with patch.object(file_ops, "stage_files", return_value=True) as mock_stage:
            result = file_ops.resolve_conflict(file_path, "resolved content")
            assert result is True
            mock_stage.assert_called_once_with(file_path)

    def test_get_file_at_commit(self, file_ops, mock_git):
        """Test getting file content at a specific commit."""
        # Mock the git show output
        mock_git._run_git_command.return_value = (0, "file content", "")

        content = file_ops.get_file_at_commit("test.txt", "abc123")
        assert content == "file content"
        mock_git._run_git_command.assert_called_with(["show", "abc123:test.txt"])

    def test_get_file_mode(self, file_ops, mock_git):
        """Test getting file mode."""
        # Mock the git ls-files output
        mock_git._run_git_command.return_value = (0, "100644 abc123 0\ttest.txt", "")

        mode = file_ops.get_file_mode("test.txt")
        assert mode == "100644"

    def test_get_file_size(self, file_ops, mock_git):
        """Test getting file size."""
        # Mock the git cat-file output
        mock_git._run_git_command.return_value = (0, "1024", "")

        size = file_ops.get_file_size("test.txt")
        assert size == 1024

    def test_get_file_type(self, file_ops, mock_git):
        """Test getting file type."""
        # Mock the git cat-file output
        mock_git._run_git_command.return_value = (0, "blob", "")

        file_type = file_ops.get_file_type("test.txt")
        assert file_type == "blob"

    def test_get_file_encoding(self, file_ops, mock_git):
        """Test getting file encoding."""
        # Test with Git attributes
        mock_git._run_git_command.return_value = (
            0,
            "test.txt: encoding: set to utf-8",
            "",
        )
        assert file_ops.get_file_encoding("test.txt") == "utf-8"

        # Test with file command (mocked subprocess)
        mock_git._run_git_command.return_value = (
            0,
            "test.txt: encoding: unspecified",
            "",
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "us-ascii"
            assert file_ops.get_file_encoding("test.txt") == "us-ascii"

    def test_get_file_attributes(self, file_ops, mock_git):
        """Test getting file attributes."""
        # Mock the git check-attr output
        mock_git._run_git_command.return_value = (
            0,
            "test.txt: diff: set\ntest.txt: merge: set\n",
            "",
        )

        attrs = file_ops.get_file_attributes("test.txt")
        assert attrs == {"diff": "set", "merge": "set"}

    def test_get_file_blame(self, file_ops, mock_git):
        """Test getting file blame information."""
        # Mock the git blame output
        blame_output = (
            "1234567890abcdef 1 1 2\n"
            "author John Doe\n"
            "author-mail <john@example.com>\n"
            "author-time 1609459200\n"
            "author-tz +0000\n"
            "committer Jane Smith\n"
            "committer-mail <jane@example.com>\n"
            "committer-time 1609459200\n"
            "committer-tz +0000\n"
            "summary Initial commit\n"
            "\tLine 1 content\n"
            "testcommit1234567890abcdef 2 2 1\n"
            "author John Doe\n"
            "author-mail <john@example.com>\n"
            "author-time 1609459200\n"
            "author-tz +0000\n"
            "committer Jane Smith\n"
            "committer-mail <jane@example.com>\n"
            "committer-time 1609459200\n"
            "committer-tz +0000\n"
            "summary Initial commit\n"
            "\tLine 2 content\n"
        )
        mock_git._run_git_command.return_value = (0, blame_output, "")

        blame = file_ops.get_file_blame("test.txt")
        assert len(blame) == 2
        # Test hash with a clear pattern to avoid secret detection
        assert blame[0]["commit"] == "testcommit1234567890abcdef"
        assert blame[0]["line"] == "Line 1 content"
        assert blame[1]["line"] == "Line 2 content"
