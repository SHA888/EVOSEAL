"""Security analysis strategy for identifying and fixing security issues."""

import ast
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional, TypeVar, Union

from ..models import EditCriteria, EditOperation, EditSuggestion
from .base_strategy import BaseEditStrategy

# Type variable for generic function type
T = TypeVar("T")


class SecurityIssueSeverity(Enum):
    """Severity levels for security issues."""

    CRITICAL = auto()
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()
    INFO = auto()


@dataclass
class SecurityConfig:
    """Configuration for the SecurityAnalysisStrategy.

    Attributes:
        enabled: Whether the strategy is enabled
        check_risky_imports: Check for potentially dangerous imports
        check_hardcoded_secrets: Check for hardcoded secrets/credentials
        check_unsafe_functions: Check for potentially unsafe function calls
        check_sql_injection: Check for potential SQL injection vulnerabilities
        check_xss: Check for potential XSS vulnerabilities
        check_command_injection: Check for potential command injection vulnerabilities
        check_file_operations: Check for potentially unsafe file operations
        ignore_patterns: Patterns to ignore in the analysis
        custom_checks: List of custom security check functions
    """

    enabled: bool = True
    check_risky_imports: bool = True
    check_hardcoded_secrets: bool = True
    check_unsafe_functions: bool = True
    check_sql_injection: bool = True
    check_xss: bool = True
    check_command_injection: bool = True
    check_file_operations: bool = True
    ignore_patterns: list[str] = field(default_factory=list)
    custom_checks: list[Callable[[str, ast.AST, dict[str, Any]], list[EditSuggestion]]] = field(
        default_factory=list
    )


class SecurityAnalysisStrategy(BaseEditStrategy):
    """Strategy for identifying and suggesting fixes for security issues."""

    # Confidence level constants
    CONFIDENCE_VERY_HIGH = 0.95
    CONFIDENCE_HIGH = 0.9
    CONFIDENCE_MEDIUM_HIGH = 0.8
    CONFIDENCE_MEDIUM = 0.7
    CONFIDENCE_CERTAIN = 1.0

    # Common dangerous patterns
    RISKY_IMPORTS = {
        "pickle",
        "cPickle",
        "subprocess",
        "os.system",
        "os.popen",
        "eval",
        "exec",
        "execfile",
        "input",
        "code.interact",
        "pty.spawn",
        "os.execl",
        "os.execle",
        "os.execlp",
        "os.execlpe",
        "os.execv",
        "os.execve",
        "os.execvp",
        "os.execvpe",
        "os.popen2",
        "os.popen3",
        "os.popen4",
        "os.startfile",
    }

    UNSAFE_FUNCTIONS = {
        "eval",
        "exec",
        "execfile",
        "input",
        "compile",
        "open",
        "os.system",
        "os.popen",
        "subprocess.call",
        "subprocess.Popen",
        "pickle.load",
        "pickle.loads",
        "cPickle.load",
        "cPickle.loads",
        "marshal.load",
        "marshal.loads",
        "yaml.load",
        "yaml.safe_load",
        "jsonpickle.decode",
        "shelve.open",
        "sqlite3.connect",
        "tempfile.mktemp",
        "tempfile.mkstemp",
        "tempfile.mkdtemp",
    }

    # Common secret patterns (simplified for example)
    SECRET_PATTERNS = [
        (r"(?i)password\s*[=:]\s*[\'\"].*?[\'\"]", "Hardcoded password"),
        (r"(?i)api[_-]?key\s*[=:]\s*[\'\"].*?[\'\"]", "Hardcoded API key"),
        (r"(?i)secret[_-]?key\s*[=:]\s*[\'\"].*?[\'\"]", "Hardcoded secret key"),
        (r"(?i)token\s*[=:]\s*[\'\"].*?[\'\"]", "Hardcoded token"),
        (r"(?i)credential\s*[=:]\s*[\'\"].*?[\'\"]", "Hardcoded credential"),
    ]

    def __init__(self, config: Optional[SecurityConfig] = None):
        """Initialize the security analysis strategy.

        Args:
            config: Configuration for the security analysis. If None, defaults will be used.
        """
        # Define constant for priority level
        security_priority = 10  # Higher priority than documentation/formatting
        super().__init__(priority=security_priority)
        self.config = config or SecurityConfig()
        self._compiled_ignore_patterns = [
            re.compile(pattern) for pattern in self.config.ignore_patterns
        ]

    def evaluate(self, content: str, **kwargs: Any) -> list[EditSuggestion]:
        """Analyze content for security issues.

        Args:
            content: The content to analyze
            **kwargs: Additional context (e.g., file path, project info)

        Returns:
            List of security-related edit suggestions
        """
        if not self.config.enabled or not content.strip():
            return []

        suggestions: list[EditSuggestion] = []

        try:
            tree = ast.parse(content)

            # Run security checks
            if self.config.check_risky_imports:
                suggestions.extend(self._check_risky_imports(tree, content))

            if self.config.check_unsafe_functions:
                suggestions.extend(self._check_unsafe_functions(tree, content))

            if self.config.check_sql_injection:
                suggestions.extend(self._check_sql_injection(tree, content))

            if self.config.check_xss:
                suggestions.extend(self._check_xss(tree, content))

            if self.config.check_command_injection:
                suggestions.extend(self._check_command_injection(tree, content))

            if self.config.check_file_operations:
                suggestions.extend(self._check_file_operations(tree, content))

            if self.config.check_hardcoded_secrets:
                suggestions.extend(self._check_hardcoded_secrets(content))

            # Run custom checks
            for check_func in self.config.custom_checks:
                try:
                    # Call the custom check function with the expected signature: (content: str, tree: ast.AST, **kwargs)
                    # Note: The type checker is confused about the signature, but this matches the SecurityConfig type
                    custom_suggestions = check_func(content, tree, **kwargs)  # type: ignore[call-arg]
                    if custom_suggestions:
                        suggestions.extend(custom_suggestions)
                except Exception as e:
                    # Log the error but don't let one failing check break the whole analysis
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Custom security check {check_func.__name__} failed: {str(e)}",
                        exc_info=True,
                    )
                    continue

        except (SyntaxError, ValueError) as e:
            # If we can't parse the content, return a syntax error suggestion
            suggestions.append(
                EditSuggestion(
                    operation=EditOperation.REWRITE,
                    criteria=[EditCriteria.SECURITY],
                    original_text=content or "",  # Ensure not None
                    suggested_text=f"# SECURITY WARNING: Syntax error in code - {str(e)}\n{content}",
                    explanation=f"Syntax error in code: {str(e)}",
                    confidence=self.CONFIDENCE_CERTAIN,
                    line_number=1,
                    metadata={"error_type": "syntax_error", "error": str(e)},
                )
            )

        return suggestions

    def _check_risky_imports(self, tree: ast.AST, content: str) -> list[EditSuggestion]:
        """Check for potentially dangerous imports."""
        suggestions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    if name.name in self.RISKY_IMPORTS and not self._is_ignored(name.name):
                        node_text = ast.get_source_segment(content, node) or f"import {name.name}"
                        suggestions.append(
                            EditSuggestion(
                                operation=EditOperation.REWRITE,
                                criteria=[EditCriteria.SECURITY],
                                original_text=node_text,
                                suggested_text=f"# SECURITY: {ast.get_source_segment(content, node)}  # REVIEW: Potentially dangerous import",
                                explanation=f"Potentially dangerous import: {name.name}",
                                confidence=0.9,
                                line_number=node.lineno,
                                metadata={
                                    "issue_type": "risky_import",
                                    "import": name.name,
                                },
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for name in node.names:
                    full_import = f"{module}.{name.name}" if module else name.name
                    if full_import in self.RISKY_IMPORTS and not self._is_ignored(full_import):
                        node_text = (
                            ast.get_source_segment(content, node)
                            or f"from {module} import {name.name}"
                        )
                        suggestions.append(
                            EditSuggestion(
                                operation=EditOperation.REWRITE,
                                criteria=[EditCriteria.SECURITY],
                                original_text=node_text,
                                suggested_text=f"# SECURITY: {ast.get_source_segment(content, node)}  # REVIEW: Potentially dangerous import",
                                explanation=f"Potentially dangerous import: {full_import}",
                                confidence=0.9,
                                line_number=node.lineno,
                                metadata={
                                    "issue_type": "risky_import",
                                    "import": full_import,
                                },
                            )
                        )

        return suggestions

    def _check_unsafe_functions(self, tree: ast.AST, content: str) -> list[EditSuggestion]:
        """Check for potentially unsafe function calls."""
        suggestions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name in self.UNSAFE_FUNCTIONS and not self._is_ignored(func_name):
                    node_text = ast.get_source_segment(content, node) or f"{node.func.id}()"
                    suggestions.append(
                        EditSuggestion(
                            operation=EditOperation.REWRITE,
                            criteria=[EditCriteria.SECURITY],
                            original_text=node_text,
                            suggested_text=f"# SECURITY: {ast.get_source_segment(content, node)}  # REVIEW: Potentially unsafe function call",
                            explanation=f"Potentially unsafe function call: {func_name}",
                            confidence=0.8,
                            line_number=node.lineno,
                            metadata={
                                "issue_type": "unsafe_function",
                                "function": func_name,
                            },
                        )
                    )

        return suggestions

    def _check_sql_injection(self, tree: ast.AST, content: str) -> list[EditSuggestion]:
        """Check for potential SQL injection vulnerabilities."""
        suggestions = []

        for node in ast.walk(tree):
            # Check for string formatting in SQL queries
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and hasattr(node.func, "attr")
                and node.func.attr in ["execute", "executemany"]
                and node.args
                and isinstance(node.args[0], (ast.JoinedStr, ast.BinOp, ast.Mod))
            ):

                suggestions.append(
                    EditSuggestion(
                        operation=EditOperation.REWRITE,
                        criteria=[EditCriteria.SECURITY],
                        original_text=ast.get_source_segment(content, node)
                        or f"{node.func.attr}()",
                        suggested_text=f"# SECURITY: {ast.get_source_segment(content, node)}  # REVIEW: Potential SQL injection - use parameterized queries",
                        explanation="Potential SQL injection vulnerability - use parameterized queries instead of string formatting",
                        confidence=0.9,
                        line_number=node.lineno,
                        metadata={"issue_type": "sql_injection"},
                    )
                )

        return suggestions

    def _check_xss(self, tree: ast.AST, content: str) -> list[EditSuggestion]:
        """Check for potential XSS vulnerabilities."""
        suggestions = []

        # Check for Flask/Jinja2 templates with unescaped variables
        for node in ast.walk(tree):
            # Check for Flask route handlers that return unescaped user input
            if isinstance(node, ast.FunctionDef) and any(
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Attribute)
                and getattr(d.func, "attr", "") == "route"
                for d in node.decorator_list
            ):

                # Look for return statements with f-strings or string formatting
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.Return) and stmt.value:
                        if isinstance(stmt.value, (ast.JoinedStr, ast.FormattedValue)) or (
                            isinstance(stmt.value, ast.Call)
                            and isinstance(stmt.value.func, ast.Attribute)
                            and stmt.value.func.attr in ["format", "format_map"]
                        ):

                            # Get the source line for context
                            source_line = ast.get_source_segment(content, stmt) or str(stmt)

                            suggestions.append(
                                EditSuggestion(
                                    operation=EditOperation.REWRITE,
                                    criteria=[EditCriteria.SECURITY],
                                    original_text=source_line,
                                    suggested_text=f"# SECURITY: {source_line}  # REVIEW: Potential XSS - escape user input with escape() or use template engine",
                                    explanation="Potential XSS vulnerability - escape user input before including in HTML/JavaScript",
                                    confidence=self.CONFIDENCE_MEDIUM_HIGH,
                                    line_number=stmt.lineno,
                                    metadata={
                                        "issue_type": "xss",
                                        "context": "flask_route",
                                    },
                                )
                            )
                            break

        # Check for direct HTML generation with user input
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and hasattr(node.func, "attr")
                and node.func.attr in ["write", "send", "respond"]
                and any(isinstance(arg, (ast.JoinedStr, ast.FormattedValue)) for arg in node.args)
            ):

                source_line = ast.get_source_segment(content, node) or str(node)
                node_text = source_line or f"Potential XSS in {node.func.attr} call"
                suggestions.append(
                    EditSuggestion(
                        operation=EditOperation.REWRITE,
                        criteria=[EditCriteria.SECURITY],
                        original_text=node_text,
                        suggested_text=f"# SECURITY: {source_line}  # REVIEW: Potential XSS - escape user input before writing to output",
                        explanation="Potential XSS vulnerability - escape user input before writing to output",
                        confidence=self.CONFIDENCE_MEDIUM,
                        line_number=node.lineno,
                        metadata={"issue_type": "xss", "context": "direct_output"},
                    )
                )

        return suggestions

    def _check_command_injection(self, tree: ast.AST, content: str) -> list[EditSuggestion]:
        """Check for potential command injection vulnerabilities."""
        suggestions = []

        for node in ast.walk(tree):
            # Check for os.system with user input
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
                and node.func.attr == "system"
                and node.args
                and isinstance(node.args[0], (ast.JoinedStr, ast.BinOp, ast.Call, ast.Name))
            ):
                node_text = ast.get_source_segment(content, node) or "os.system()"
                suggestions.append(
                    EditSuggestion(
                        operation=EditOperation.REWRITE,
                        criteria=[EditCriteria.SECURITY],
                        original_text=node_text,
                        suggested_text=f"# SECURITY: {node_text}  # REVIEW: Potential command injection - use subprocess with shell=False",
                        explanation="Potential command injection vulnerability - use subprocess with shell=False and pass arguments as a list",
                        confidence=0.9,
                        line_number=node.lineno,
                        metadata={"issue_type": "command_injection"},
                    )
                )

        return suggestions

    def _check_file_operations(self, tree: ast.AST, content: str) -> list[EditSuggestion]:
        """Check for potentially unsafe file operations."""
        suggestions = []

        for node in ast.walk(tree):
            # Check for open() with user-controlled paths
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "open"
                and node.args
                and isinstance(node.args[0], (ast.JoinedStr, ast.BinOp, ast.Call, ast.Name))
            ):
                node_text = ast.get_source_segment(content, node) or "open()"
                suggestions.append(
                    EditSuggestion(
                        operation=EditOperation.REWRITE,
                        criteria=[EditCriteria.SECURITY],
                        original_text=node_text,
                        suggested_text=f"# SECURITY: {node_text}  # REVIEW: Validate file path before opening",
                        explanation="Potential security issue - validate file paths before opening files",
                        confidence=0.8,
                        line_number=node.lineno,
                        metadata={"issue_type": "file_operation"},
                    )
                )

        return suggestions

    def _check_hardcoded_secrets(self, content: str) -> list[EditSuggestion]:
        """Check for hardcoded secrets and credentials."""
        suggestions = []

        for line_num, line in enumerate(content.split("\n"), 1):
            for pattern, description in self.SECRET_PATTERNS:
                if re.search(pattern, line) and not self._is_ignored(line):
                    suggestions.append(
                        EditSuggestion(
                            operation=EditOperation.REWRITE,
                            criteria=[EditCriteria.SECURITY],
                            original_text=line,
                            suggested_text=f"# SECURITY: {line}  # REVIEW: {description} - move to configuration/environment variables",
                            explanation=f"{description} found in code - store secrets in environment variables or secure configuration",
                            confidence=self.CONFIDENCE_VERY_HIGH,  # Very high confidence for hardcoded secrets
                            line_number=line_num,
                            metadata={
                                "issue_type": "hardcoded_secret",
                                "description": description,
                            },
                        )
                    )

        return suggestions

    def _is_ignored(self, text: str) -> bool:
        """Check if text matches any ignore patterns."""
        return any(pattern.search(text) for pattern in self._compiled_ignore_patterns)

    def get_config(self) -> dict[str, Any]:
        """Get the current configuration as a dictionary."""
        return {
            "enabled": self.config.enabled,
            "check_risky_imports": self.config.check_risky_imports,
            "check_hardcoded_secrets": self.config.check_hardcoded_secrets,
            "check_unsafe_functions": self.config.check_unsafe_functions,
            "check_sql_injection": self.config.check_sql_injection,
            "check_xss": self.config.check_xss,
            "check_command_injection": self.config.check_command_injection,
            "check_file_operations": self.config.check_file_operations,
            "ignore_patterns": self.config.ignore_patterns,
            "custom_checks_count": len(self.config.custom_checks),
        }
