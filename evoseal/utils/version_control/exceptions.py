"""
Git-related exceptions for the EVOSEAL version control system.
"""


class GitError(Exception):
    """Base class for all Git-related exceptions."""

    pass


class AuthenticationError(GitError):
    """Raised when authentication fails."""

    pass


class SSHAuthenticationError(AuthenticationError):
    """Raised when SSH authentication fails."""

    pass


class HTTPSAuthenticationError(AuthenticationError):
    """Raised when HTTPS authentication fails."""

    pass


class RepositoryNotFoundError(GitError):
    """Raised when a repository is not found."""

    pass


class BranchNotFoundError(GitError):
    """Raised when a branch is not found."""

    pass


class MergeConflictError(GitError):
    """Raised when a merge conflict occurs."""

    pass


class PushRejectedError(GitError):
    """Raised when a push is rejected by the remote."""

    pass


class InvalidGitRepositoryError(GitError):
    """Raised when an invalid Git repository is encountered."""

    pass


class GitCommandError(GitError):
    """Raised when a Git command fails."""

    def __init__(
        self, message: str, command: str, returncode: int, stdout: str = "", stderr: str = ""
    ):
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"{message}\nCommand: {command}\nExit code: {returncode}\n{stderr}")


class GitOperationError(GitError):
    """Raised when a Git operation fails."""

    def __init__(self, operation: str, message: str, details: str = ""):
        self.operation = operation
        self.details = details
        super().__init__(
            f"{operation} failed: {message}\n{details}"
            if details
            else f"{operation} failed: {message}"
        )
