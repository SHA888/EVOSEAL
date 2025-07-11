"""
File Operations Module for Git

This module provides functionality for file-level Git operations including staging,
unstaging, checking file status, and handling file conflicts.
"""

import logging
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .exceptions import GitCommandError, GitError

logger = logging.getLogger(__name__)


class FileStatus(Enum):
    """Enum representing the status of a file in the working directory."""

    UNTRACKED = auto()
    MODIFIED = auto()
    STAGED = auto()
    DELETED = auto()
    RENAMED = auto()
    COPIED = auto()
    UPDATED_BUT_UNMERGED = auto()
    IGNORED = auto()


@dataclass
class FileInfo:
    """Data class containing information about a file in the repository."""

    path: Path
    status: FileStatus
    staged: bool = False
    conflicts: bool = False
    original_path: Optional[Path] = None
    similarity: Optional[int] = None
    similarity: Optional[int] = None


class FileOperations:
    """
    Handles file-level Git operations.

    This class provides methods for staging, unstaging, and checking the status
    of files in a Git repository.
    """

    def __init__(self, git_interface):
        """Initialize with a Git interface instance.

        Args:
            git_interface: An instance of a class that implements GitInterface
        """
        self.git = git_interface

    def stage_files(self, *file_paths: Union[str, Path]) -> bool:
        """Stage one or more files for commit.

        Args:
            *file_paths: One or more file paths to stage

        Returns:
            bool: True if successful, False otherwise

        Raises:
            GitError: If there's an error executing the Git command
        """
        if not file_paths:
            return False

        paths = [str(Path(p)) for p in file_paths]
        try:
            self.git._run_git_command(['add', '--'] + paths)
            return True
        except GitCommandError as e:
            logger.error(f"Error staging files {paths}: {e}")
            return False

    def unstage_files(self, *file_paths: Union[str, Path]) -> bool:
        """Unstage one or more files.

        Args:
            *file_paths: One or more file paths to unstage

        Returns:
            bool: True if successful, False otherwise

        Raises:
            GitError: If there's an error executing the Git command
        """
        if not file_paths:
            return False

        paths = [str(Path(p)) for p in file_paths]
        try:
            self.git._run_git_command(['restore', '--staged', '--'] + paths)
            return True
        except GitCommandError as e:
            logger.error(f"Error unstaging files {paths}: {e}")
            return False

    def get_file_status(self, file_path: Union[str, Path]) -> Optional[FileInfo]:
        """Get the status of a specific file.

        Args:
            file_path: Path to the file to check

        Returns:
            Optional[FileInfo]: FileInfo object with status information, or None if file not found
        """
        file_path = Path(file_path)
        status = self.get_status()
        return status.get(file_path)

    def get_status(self) -> Dict[Path, FileInfo]:
        """Get the status of all files in the repository.

        Returns:
            Dict[Path, FileInfo]: Dictionary mapping file paths to their status information
        """
        try:
            # Get the status in porcelain v2 format for easier parsing
            result = self.git._run_git_command(['status', '--porcelain=v2', '--ignored'])
            return self._parse_status_output(result[1])  # result[1] is stdout
        except GitCommandError as e:
            logger.error(f"Error getting file status: {e}")
            return {}

    def _parse_status_output(self, status_output: str) -> Dict[Path, FileInfo]:
        """Parse the output of 'git status --porcelain=v2' into a dictionary of FileInfo objects.

        Args:
            status_output: Output from 'git status --porcelain=v2'

        Returns:
            Dict[Path, FileInfo]: Dictionary mapping file paths to their status information
        """
        status_map = {}

        for line in status_output.splitlines():
            if not line.strip():
                continue

            # Parse the status line
            parts = line.split()
            if not parts:
                continue

            # Parse the status code
            status_code = parts[0]

            # Handle different status formats
            if status_code == '1':  # Regular changed files
                # Format: 1 <XY> <sub> <mH> <mI> <mW> <hH> <hI> <path> [<orig_path>]
                if len(parts) < 9:
                    continue

                xy = parts[1]

                # For renames and copies, the last two parts are the original and new paths
                if ('R' in xy or 'C' in xy) and len(parts) >= 10:
                    # Rename or copy: 1 R. N... 100644 100644 100644 1234567 1234567 1234567 old.txt new.txt
                    # The path is the last part, and the original path is the second to last part
                    path = parts[-1]
                    orig_path = parts[-2]
                    status = self._parse_status_xy(xy)
                    file_info = FileInfo(
                        path=Path(path),
                        status=status,
                        staged=' ' not in xy[0],  # First char is not space if staged
                        original_path=Path(orig_path),
                    )
                    status_map[Path(path)] = file_info
                else:
                    # Regular modified file: 1 M. N... 100644 100644 100644 1234567 1234567 1234567 file.txt
                    # The path is the last part
                    path = parts[-1]
                    status = self._parse_status_xy(xy)
                    file_info = FileInfo(
                        path=Path(path),
                        status=status,
                        staged=' ' not in xy[0],  # First char is not space if staged
                        original_path=None,
                    )
                    status_map[Path(path)] = file_info

            elif status_code.startswith('2'):  # Renamed/Copied files
                # Format: 2 <XY> <sub> <mH> <mI> <mW> <hH> <hI> <X><score> <path1> <path2>
                if len(parts) < 11:
                    continue

                xy = parts[1]
                path1 = parts[9]
                path2 = parts[10]

                status = self._parse_status_xy(xy)
                file_info = FileInfo(
                    path=Path(path2),
                    status=status,
                    staged=' ' not in xy[0],  # First char is not space if staged
                    original_path=Path(path1) if path1 != path2 else None,
                    similarity=(
                        int(parts[8][1:]) if len(parts) > 8 and parts[8].startswith('R') else None
                    ),
                )
                status_map[Path(path2)] = file_info

            elif status_code.startswith('?') or status_code.startswith(
                '!'
            ):  # Untracked/Ignored files
                path = parts[1] if len(parts) > 1 else None
                if not path:
                    continue

                status = FileStatus.UNTRACKED if status_code.startswith('?') else FileStatus.IGNORED
                file_info = FileInfo(path=Path(path), status=status, staged=False)
                status_map[Path(path)] = file_info

        return status_map

    def _parse_status_xy(self, xy: str) -> FileStatus:
        """Parse the XY status code from git status.

        Args:
            xy: Two-character status code from git status

        Returns:
            FileStatus: The corresponding FileStatus enum value
        """
        if len(xy) < 2:
            return FileStatus.MODIFIED

        x = xy[0]  # Index status
        y = xy[1]  # Working tree status

        # Check for merge conflicts first
        if x == 'U' or y == 'U' or (x == 'A' and y == 'A') or (x == 'D' and y == 'D'):
            return FileStatus.UPDATED_BUT_UNMERGED

        # Check for staged changes
        if x != ' ':
            if x == 'M':
                return FileStatus.MODIFIED
            elif x == 'A':
                return FileStatus.STAGED
            elif x == 'D':
                return FileStatus.DELETED
            elif x == 'R':
                return FileStatus.RENAMED
            elif x == 'C':
                return FileStatus.COPIED

        # Check for unstaged changes
        if y == 'M':
            return FileStatus.MODIFIED
        elif y == 'D':
            return FileStatus.DELETED

        return FileStatus.MODIFIED  # Default to modified if we can't determine

    def get_file_diff(self, file_path: Union[str, Path], staged: bool = False) -> Optional[str]:
        """Get the diff for a specific file.

        Args:
            file_path: Path to the file to get the diff for
            staged: Whether to get the staged diff (True) or working tree diff (False)

        Returns:
            Optional[str]: The diff as a string, or None if there's an error
        """
        file_path = Path(file_path)
        try:
            cmd = ['diff', '--no-ext-diff', '--']
            if staged:
                cmd.insert(1, '--staged')

            cmd.append(str(file_path))
            result = self.git._run_git_command(cmd)
            return result[1]  # Return stdout
        except GitCommandError as e:
            logger.error(f"Error getting diff for {file_path}: {e}")
            return None

    def get_file_history(
        self, file_path: Union[str, Path], limit: int = 10
    ) -> List[Dict[str, str]]:
        """Get the commit history for a specific file.

        Args:
            file_path: Path to the file to get history for
            limit: Maximum number of commits to return

        Returns:
            List[Dict[str, str]]: List of dictionaries containing commit information
        """
        file_path = Path(file_path)
        try:
            # Format: %H: %s (%an, %ad)
            format_str = '%H|||%s|||%an|||%ad'
            cmd = [
                'log',
                f'-n {limit}',
                f'--pretty=format:{format_str}',
                '--date=iso',
                '--',
                str(file_path),
            ]

            result = self.git._run_git_command(cmd)
            if not result[1]:  # Empty stdout
                return []

            history = []
            for line in result[1].splitlines():
                if not line.strip():
                    continue

                parts = line.split('|||', 3)
                if len(parts) != 4:
                    continue

                commit_hash, subject, author, date = parts
                history.append(
                    {'hash': commit_hash, 'subject': subject, 'author': author, 'date': date}
                )

            return history

        except GitCommandError as e:
            logger.error(f"Error getting history for {file_path}: {e}")
            return []

    def is_binary_file(self, file_path: Union[str, Path]) -> bool:
        """Check if a file is a binary file.

        Args:
            file_path: Path to the file to check

        Returns:
            bool: True if the file is binary, False otherwise or if there's an error
        """
        file_path = Path(file_path)
        try:
            # Use git diff --numstat to detect binary files
            result = self.git._run_git_command(['diff', '--numstat', '--', str(file_path)])
            if not result[1]:  # Empty output means file is not in git or no changes
                return False

            # Binary files will have a - in the output, e.g., "-\t-\tpath/to/file.bin"
            for line in result[1].splitlines():
                if line.startswith('-\t-\t'):
                    return True

            return False

        except GitCommandError as e:
            logger.error(f"Error checking if file is binary: {e}")
            return False

    def get_conflicted_files(self) -> List[Path]:
        """Get a list of files with merge conflicts.

        Returns:
            List[Path]: List of paths to files with conflicts
        """
        try:
            # Get unmerged files
            result = self.git._run_git_command(['diff', '--name-only', '--diff-filter=U'])
            if not result[1]:  # No conflicts
                return []

            return [Path(p) for p in result[1].splitlines() if p.strip()]

        except GitCommandError as e:
            logger.error(f"Error getting conflicted files: {e}")
            return []

    def resolve_conflict(self, file_path: Union[str, Path], content: str) -> bool:
        """Resolve a merge conflict by providing the resolved content.

        Args:
            file_path: Path to the file with conflicts
            content: The resolved content of the file

        Returns:
            bool: True if successful, False otherwise
        """
        file_path = Path(file_path)
        try:
            # Write the resolved content to the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # Stage the resolved file
            self.stage_files(file_path)
            return True

        except (IOError, OSError) as e:
            logger.error(f"Error writing to file {file_path}: {e}")
            return False
        except GitCommandError as e:
            logger.error(f"Error staging resolved file {file_path}: {e}")
            return False

    def get_file_at_commit(
        self, file_path: Union[str, Path], commit: str = 'HEAD'
    ) -> Optional[str]:
        """Get the content of a file at a specific commit.

        Args:
            file_path: Path to the file to get
            commit: Commit hash or reference (default: 'HEAD')

        Returns:
            Optional[str]: The file content, or None if not found
        """
        file_path = Path(file_path)
        try:
            result = self.git._run_git_command(['show', f'{commit}:{file_path}'])
            return result[1]  # Return stdout
        except GitCommandError as e:
            logger.error(f"Error getting file {file_path} at commit {commit}: {e}")
            return None

    def get_file_mode(self, file_path: Union[str, Path]) -> Optional[str]:
        """Get the file mode (permissions) from Git's index.

        Args:
            file_path: Path to the file

        Returns:
            Optional[str]: The file mode (e.g., '100644'), or None if not found
        """
        file_path = Path(file_path)
        try:
            result = self.git._run_git_command(['ls-files', '--stage', '--', str(file_path)])
            if not result[1]:
                return None

            # Format: <mode> <hash> <stage>\t<file>
            parts = result[1].strip().split()
            if len(parts) >= 1:
                return parts[0]  # Mode is the first part

            return None

        except GitCommandError as e:
            logger.error(f"Error getting file mode for {file_path}: {e}")
            return None

    def get_file_size(self, file_path: Union[str, Path]) -> Optional[int]:
        """Get the size of a file in bytes from Git's index.

        Args:
            file_path: Path to the file

        Returns:
            Optional[int]: Size in bytes, or None if not found
        """
        file_path = Path(file_path)
        try:
            result = self.git._run_git_command(['cat-file', '-s', f'HEAD:{file_path}'])
            if not result[1]:
                return None

            return int(result[1].strip())

        except (GitCommandError, ValueError) as e:
            logger.error(f"Error getting file size for {file_path}: {e}")
            return None

    def get_file_type(self, file_path: Union[str, Path]) -> Optional[str]:
        """Get the type of a file (blob, symlink, etc.) from Git's index.

        Args:
            file_path: Path to the file

        Returns:
            Optional[str]: The file type, or None if not found
        """
        file_path = Path(file_path)
        try:
            result = self.git._run_git_command(['cat-file', '-t', f'HEAD:{file_path}'])
            return result[1].strip() if result[1] else None

        except GitCommandError as e:
            logger.error(f"Error getting file type for {file_path}: {e}")
            return None

    def get_file_encoding(self, file_path: Union[str, Path]) -> Optional[str]:
        """Attempt to detect the encoding of a file.

        This is a best-effort detection and may not be 100% accurate.

        Args:
            file_path: Path to the file

        Returns:
            Optional[str]: The detected encoding, or None if detection fails
        """
        file_path = Path(file_path)
        try:
            # First check if Git has a guess for the encoding
            result = self.git._run_git_command(['check-attr', 'encoding', '--', str(file_path)])
            if result[1]:
                # Parse output like: 'test.txt: encoding: set to utf-8'
                for line in result[1].splitlines():
                    if 'encoding: set to ' in line:
                        encoding = line.split('set to ')[1].strip()
                        if encoding != 'unspecified':
                            return encoding

                # Fall back to file command for detection
                import subprocess  # nosec: B404  # subprocess is needed for file command

                try:
                    result = subprocess.run(
                        ['file', '--mime-encoding', '--brief', str(file_path)],
                        capture_output=True,
                        text=True,
                        check=True,
                    )  # nosec: B607, B603  # file command is safe, no user input
                    return result.stdout.strip()
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass

            return None

        except GitCommandError as e:
            logger.error(f"Error getting file encoding for {file_path}: {e}")
            return None

    def get_file_attributes(self, file_path: Union[str, Path]) -> Dict[str, str]:
        """Get all Git attributes for a file.

        Args:
            file_path: Path to the file

        Returns:
            Dict[str, str]: Dictionary of attribute names and their values
        """
        file_path = Path(file_path)
        try:
            result = self.git._run_git_command(['check-attr', '-a', '--', str(file_path)])
            if not result[1]:
                return {}

            attributes = {}
            for line in result[1].splitlines():
                if ':' not in line:
                    continue

                # Format: <file>: <attribute>: <value>
                parts = line.split(':', 2)
                if len(parts) == 3:
                    attr = parts[1].strip()
                    value = parts[2].strip()
                    if value.startswith('set: '):
                        value = value[5:]
                    attributes[attr] = value

            return attributes

        except GitCommandError as e:
            logger.error(f"Error getting attributes for {file_path}: {e}")
            return {}

    def get_file_blame(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Get blame information for a file.

        Args:
            file_path: Path to the file

        Returns:
            List[Dict[str, Any]]: List of blame entries with commit and line information
        """
        file_path = Path(file_path)
        try:
            # Use porcelain v2 format for easier parsing
            result = self.git._run_git_command(
                ['blame', '--porcelain', '--line-porcelain', '--', str(file_path)]
            )

            if not result[1]:
                return []

            blame_entries = []
            current_entry = None

            for line in result[1].splitlines():
                if not line:
                    continue

                if line[0] == '\t':
                    # This is the line content
                    if current_entry:
                        current_entry['line'] = line[1:]
                        blame_entries.append(current_entry)
                        current_entry = None
                    continue

                # Parse the header line
                parts = line.split()
                if len(parts) < 3:
                    continue

                commit_hash = parts[0]
                try:
                    original_line = int(parts[1])
                    final_line = int(parts[2])
                except (ValueError, IndexError):
                    continue

                current_entry = {
                    'commit': commit_hash,
                    'original_line': original_line,
                    'final_line': final_line,
                    'line': '',
                    'author': '',
                    'author_mail': '',
                    'author_time': '',
                    'summary': '',
                }

                # The next lines will contain more information about this commit
                # which will be processed in the next iteration

            return blame_entries

        except GitCommandError as e:
            logger.error(f"Error getting blame for {file_path}: {e}")
            return []
