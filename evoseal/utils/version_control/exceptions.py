"""
Git-related exceptions for the EVOSEAL version control system.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar, Union


class ErrorSeverity(Enum):
    """Severity levels for Git errors."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Categories for Git errors."""
    AUTHENTICATION = "authentication"
    NETWORK = "network"
    VALIDATION = "validation"
    CONFLICT = "conflict"
    PERMISSION = "permission"
    RESOURCE = "resource"
    CONFIGURATION = "configuration"
    INTEGRITY = "integrity"
    OPERATION = "operation"


@dataclass
class ErrorContext:
    """Contextual information about an error."""
    operation: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    command: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    recovery_suggestions: List[str] = field(default_factory=list)


class GitError(Exception):
    """Base class for all Git-related exceptions."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.OPERATION,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
    ):
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context
        self.cause = cause
        self.timestamp = datetime.utcnow()
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the error message with context."""
        msg = [f"{self.__class__.__name__}: {self.message}"]
        if self.context and self.context.operation:
            msg.append(f"\nOperation: {self.context.operation}")
        if self.context and self.context.command:
            msg.append(f"\nCommand: {self.context.command}")
        if self.cause:
            msg.append(f"\nCaused by: {str(self.cause)}")
        if self.context and self.context.details:
            msg.append("\nDetails:")
            for key, value in self.context.details.items():
                msg.append(f"\n  {key}: {value}")
        if self.context and self.context.recovery_suggestions:
            msg.append("\n\nRecovery suggestions:")
            for i, suggestion in enumerate(self.context.recovery_suggestions, 1):
                msg.append(f"\n  {i}. {suggestion}")
        return "".join(msg)

    def with_context(self, **kwargs) -> 'GitError':
        """Add context to the error."""
        if not self.context:
            self.context = ErrorContext(operation=kwargs.pop('operation', 'unknown'))
        
        for key, value in kwargs.items():
            if key == 'details' and isinstance(value, dict):
                self.context.details.update(value)
            elif hasattr(self.context, key):
                setattr(self.context, key, value)
        
        # Reformat the message with new context
        self.args = (self._format_message(),)
        return self

    def add_recovery_suggestion(self, suggestion: str) -> None:
        """Add a recovery suggestion to the error."""
        if not self.context:
            self.context = ErrorContext(operation='unknown')
        self.context.recovery_suggestions.append(suggestion)
        # Update the message with the new suggestion
        self.args = (self._format_message(),)


class AuthenticationError(GitError):
    """Raised when authentication fails."""
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        # Add common recovery suggestions for authentication errors
        self.add_recovery_suggestion("Verify your credentials and try again")
        self.add_recovery_suggestion("Check if your authentication token has expired")
        self.add_recovery_suggestion("Ensure you have the necessary permissions")


class SSHAuthenticationError(AuthenticationError):
    """Raised when SSH authentication fails."""
    def __init__(self, message: str = "SSH authentication failed", **kwargs):
        super().__init__(message, **kwargs)
        self.add_recovery_suggestion("Verify your SSH key is correctly configured")
        self.add_recovery_suggestion("Ensure your SSH agent is running and has the key loaded")
        self.add_recovery_suggestion("Check if the remote repository accepts your SSH key")


class HTTPSAuthenticationError(AuthenticationError):
    """Raised when HTTPS authentication fails."""
    def __init__(self, message: str = "HTTPS authentication failed", **kwargs):
        super().__init__(message, **kwargs)
        self.add_recovery_suggestion("Verify your username and password/token")
        self.add_recovery_suggestion("If using a personal access token, ensure it has the required scopes")
        self.add_recovery_suggestion("Check if your credentials are cached or need to be updated")


class NetworkError(GitError):
    """Raised for network-related errors."""
    def __init__(self, message: str = "Network operation failed", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.add_recovery_suggestion("Check your internet connection")
        self.add_recovery_suggestion("Verify the remote repository URL is correct")
        self.add_recovery_suggestion("If using a proxy, ensure it's properly configured")


class RepositoryNotFoundError(GitError):
    """Raised when a repository is not found."""
    def __init__(self, message: str = "Repository not found", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.add_recovery_suggestion("Verify the repository URL is correct")
        self.add_recovery_suggestion("Check if you have access to the repository")
        self.add_recovery_suggestion("Ensure the repository exists and is accessible")


class BranchNotFoundError(GitError):
    """Raised when a branch is not found."""
    def __init__(self, message: str = "Branch not found", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.add_recovery_suggestion("Check if the branch name is correct")
        self.add_recovery_suggestion("Fetch the latest changes from remote")
        self.add_recovery_suggestion("List available branches to verify the name")


class MergeConflictError(GitError):
    """Raised when a merge conflict occurs."""
    def __init__(self, message: str = "Merge conflict detected", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.CONFLICT,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.add_recovery_suggestion("Resolve the conflicts in the affected files")
        self.add_recovery_suggestion("Mark files as resolved with 'git add'")
        self.add_recovery_suggestion("Complete the merge with 'git commit'")


class PushRejectedError(GitError):
    """Raised when a push is rejected by the remote."""
    def __init__(self, message: str = "Push was rejected", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.PERMISSION,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.add_recovery_suggestion("Fetch and merge the remote changes first")
        self.add_recovery_suggestion("Use 'git pull --rebase' to rebase your changes")
        self.add_recovery_suggestion("Check if you have push permissions to the repository")


class InvalidGitRepositoryError(GitError):
    """Raised when an invalid Git repository is encountered."""
    def __init__(self, message: str = "Not a valid Git repository", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.add_recovery_suggestion("Ensure you're in a Git repository directory")
        self.add_recovery_suggestion("Run 'git init' to initialize a new repository")
        self.add_recovery_suggestion("Check if the .git directory exists and is valid")


class GitCommandError(GitError):
    """Raised when a Git command fails."""
    def __init__(
        self,
        message: str,
        command: str,
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        **kwargs
    ):
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        
        # Create context with command details
        context = kwargs.pop('context', None) or ErrorContext(
            operation="git_command",
            command=command,
            details={
                'returncode': returncode,
                'stdout': stdout[:1000] + ('...' if len(stdout) > 1000 else ''),
                'stderr': stderr[:1000] + ('...' if len(stderr) > 1000 else '')
            }
        )
        
        super().__init__(
            message=message or f"Git command failed with return code {returncode}",
            category=ErrorCategory.OPERATION,
            severity=GitCommandError._determine_severity(returncode, stderr),
            context=context,
            **kwargs
        )
        
        # Add common recovery suggestions based on error code
        if returncode == 128 and 'Permission denied' in stderr:
            self.add_recovery_suggestion("Verify your SSH key is properly configured")
            self.add_recovery_suggestion("Check if your SSH agent is running")
            self.add_recovery_suggestion("Ensure your public key is added to the remote service")
        elif returncode == 128 and 'Repository not found' in stderr:
            self.add_recovery_suggestion("Verify the repository URL is correct")
            self.add_recovery_suggestion("Check if you have access to the repository")
        elif returncode == 1 and 'merge conflict' in stderr.lower():
            self.add_recovery_suggestion("Resolve the merge conflicts in the affected files")
            self.add_recovery_suggestion("Use 'git status' to see the list of conflicts")
    
    @staticmethod
    def _determine_severity(returncode: int, stderr: str) -> ErrorSeverity:
        """Determine the severity of a Git command error."""
        if returncode == 0:
            return ErrorSeverity.LOW
        elif returncode == 1:  # General error
            if 'merge conflict' in stderr.lower():
                return ErrorSeverity.MEDIUM
            return ErrorSeverity.LOW
        elif returncode == 128:  # Fatal error
            if 'Permission denied' in stderr or 'Authentication failed' in stderr:
                return ErrorSeverity.HIGH
            return ErrorSeverity.MEDIUM
        return ErrorSeverity.MEDIUM


class GitOperationError(GitError):
    """Raised when a Git operation fails."""
    def __init__(
        self,
        operation: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        **kwargs
    ):
        context = ErrorContext(
            operation=operation,
            details=details or {},
            recovery_suggestions=kwargs.pop('recovery_suggestions', [])
        )
        
        super().__init__(
            message=message,
            category=ErrorCategory.OPERATION,
            severity=kwargs.pop('severity', ErrorSeverity.MEDIUM),
            context=context,
            cause=cause,
            **kwargs
        )


class GitConfigError(GitError):
    """Raised for Git configuration errors."""
    def __init__(self, message: str = "Git configuration error", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.add_recovery_suggestion("Check your Git configuration with 'git config --list'")
        self.add_recovery_suggestion("Verify required Git settings are properly configured")


class GitIntegrityError(GitError):
    """Raised when Git repository integrity is compromised."""
    def __init__(self, message: str = "Git repository integrity error", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.INTEGRITY,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.add_recovery_suggestion("Run 'git fsck' to check repository integrity")
        self.add_recovery_suggestion("Consider cloning the repository again if the issue persists")


class GitPermissionError(GitError):
    """Raised when a permission-related error occurs."""
    def __init__(self, message: str = "Permission denied", **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.PERMISSION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.add_recovery_suggestion("Check file and directory permissions")
        self.add_recovery_suggestion("Ensure the current user has the necessary permissions")
        self.add_recovery_suggestion("Run with elevated privileges if required")
