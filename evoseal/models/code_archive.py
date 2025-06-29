"""Data models for code archives in EVOSEAL.

This module defines the CodeArchive model for storing and managing code snippets
with associated metadata.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, ClassVar, TypeVar, cast
from uuid import UUID, uuid4

from packaging import version as pkg_version
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel
from pydantic.functional_validators import ModelWrapValidatorHandler

# Type variables for the model class
ModelT = TypeVar("ModelT", bound="CodeArchive")
T = TypeVar("T", bound="CodeArchive")


class CodeLanguage(str, Enum):
    """Supported programming languages for code snippets."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    C = "c"
    CPP = "cpp"
    CSHARP = "csharp"
    RUBY = "ruby"
    PHP = "php"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    SCALA = "scala"
    DART = "dart"
    BASH = "bash"
    POWERSHELL = "powershell"
    SQL = "sql"
    HTML = "html"
    CSS = "css"
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    MARKDOWN = "markdown"
    TEXT = "text"
    OTHER = "other"


class CodeVisibility(str, Enum):
    """Visibility settings for code archives."""

    PRIVATE = "private"
    PUBLIC = "public"
    UNLISTED = "unlisted"


class CodeArchive(BaseModel):
    """Represents a versioned piece of code with metadata.

    Attributes:
        id: Unique identifier for the code archive
        content: The actual code content
        language: Programming language of the code
        title: Title of the code archive
        description: Description of the code
        author_id: ID of the author/owner
        created_at: When the archive was created
        updated_at: When the archive was last updated
        version: Version string (should follow semantic versioning)
        tags: List of tags for categorization
        visibility: Visibility setting (public/private)
        metadata: Additional metadata as key-value pairs
        parent_id: ID of the parent archive (for forks/versions)
        dependencies: List of dependency IDs
        is_archived: Whether the archive is archived/read-only
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(..., min_length=1)
    language: CodeLanguage = CodeLanguage.PYTHON
    title: str = Field(..., min_length=1)
    description: str = ""
    author_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0.0"
    tags: list[str] = Field(default_factory=list)
    visibility: CodeVisibility = CodeVisibility.PRIVATE
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_id: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    is_archived: bool = False

    model_config: ClassVar[ConfigDict] = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
            Enum: lambda v: v.value,
        }
    )

    def __init__(self, **data: Any) -> None:
        """Initialize the code archive with default values."""
        # Set default values
        if "id" not in data:
            data["id"] = str(uuid4())
        if "created_at" not in data:
            data["created_at"] = datetime.now(timezone.utc)
        if "updated_at" not in data:
            data["updated_at"] = data["created_at"]
        if "version" not in data:
            data["version"] = "1.0.0"
        if "tags" not in data:
            data["tags"] = []
        if "visibility" not in data:
            data["visibility"] = CodeVisibility.PRIVATE
        if "is_archived" not in data:
            data["is_archived"] = False
        if "dependencies" not in data:
            data["dependencies"] = []
        if "metadata" not in data:
            data["metadata"] = {}

        super().__init__(**data)

    @field_validator("content")
    @classmethod
    def validate_content_not_empty(cls: type[ModelT], v: str) -> str:
        """Validate that content is not empty."""
        if not v.strip():
            raise ValueError("Code content cannot be empty")
        return v

    @field_validator("title")
    @classmethod
    def validate_title_not_empty(cls: type[ModelT], v: str) -> str:
        """Validate that title is not empty."""
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

    @field_validator("version")
    @classmethod
    def validate_version_not_empty(cls: type[ModelT], v: str) -> str:
        """Validate that version is not empty."""
        if not v.strip():
            raise ValueError("Version cannot be empty")
        return v.strip()

    @field_validator("version")
    @classmethod
    def validate_version(cls: type[ModelT], v: str) -> str:
        """Validate that version follows semantic versioning."""
        if v == "latest":
            return v

        try:
            pkg_version.Version(v)
        except pkg_version.InvalidVersion as e:
            raise ValueError(
                f"Invalid version format: {v}. Must follow semantic versioning (e.g., '1.0.0')"
            ) from e
        return v

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls: type[ModelT], v: datetime | str | None) -> datetime | None:
        """Ensure datetime fields are timezone-aware.

        Args:
            v: Input value which could be a datetime, string, or None

        Returns:
            Timezone-aware datetime or None

        Raises:
            ValueError: If the input cannot be converted to a datetime
        """
        if v is None:
            return None

        dt = None
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid datetime string format: {v}") from e
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError(f"Expected datetime or ISO format string, got {type(v).__name__}")

        # Ensure timezone is set to UTC if not already set
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @field_serializer("created_at", "updated_at", when_used="json")
    def serialize_dt(self: ModelT, dt: datetime | None, _info: Any = None) -> str | None:
        """Serialize datetime fields to ISO format."""
        if dt is None:
            return None
        return dt.isoformat()

    @field_serializer("language", "visibility", when_used="json")
    def serialize_enum(self: ModelT, value: Enum, _info: Any = None) -> str:
        """Serialize enum fields to their values.

        Args:
            value: The enum value to serialize.
            _info: Additional serialization info (unused).

        Returns:
            The string representation of the enum value.
        """
        return str(value.value)

    def to_dict(self: CodeArchive, **kwargs: Any) -> dict[str, Any]:
        """Convert the model to a dictionary.

        Args:
            **kwargs: Additional arguments to pass to model_dump.

        Returns:
            dict: Dictionary representation of the model.
        """
        return dict(self.model_dump(**kwargs))

    def bump_version(self, part: str = "patch") -> str:
        """Bump the version number.

        Args:
            part: Which part to bump ('major', 'minor', or 'patch')

        Returns:
            The new version string

        Raises:
            ValueError: If the current version is not valid semantic versioning
            ValueError: If part is not one of 'major', 'minor', 'patch'
        """
        if self.version == "latest":
            raise ValueError("Cannot bump 'latest' version")

        try:
            current = pkg_version.Version(self.version)
        except pkg_version.InvalidVersion as e:
            raise ValueError(f"Cannot bump invalid version: {self.version}") from e

        major, minor, patch = current.major, current.minor, current.micro

        if part == "major":
            major += 1
            minor = 0
            patch = 0
        elif part == "minor":
            minor += 1
            patch = 0
        elif part == "patch":
            patch += 1
        else:
            raise ValueError("Part must be one of: 'major', 'minor', 'patch'")

        self.version = f"{major}.{minor}.{patch}"
        return self.version

    def get_file_extension(self) -> str:
        """Get the file extension for the code based on its language."""
        return {
            CodeLanguage.PYTHON: ".py",
            CodeLanguage.JAVASCRIPT: ".js",
            CodeLanguage.TYPESCRIPT: ".ts",
            CodeLanguage.JAVA: ".java",
            CodeLanguage.C: ".c",
            CodeLanguage.CPP: ".cpp",
            CodeLanguage.CSHARP: ".cs",
            CodeLanguage.RUBY: ".rb",
            CodeLanguage.PHP: ".php",
            CodeLanguage.SWIFT: ".swift",
            CodeLanguage.KOTLIN: ".kt",
            CodeLanguage.SCALA: ".scala",
            CodeLanguage.DART: ".dart",
            CodeLanguage.BASH: ".sh",
            CodeLanguage.POWERSHELL: ".ps1",
            CodeLanguage.SQL: ".sql",
            CodeLanguage.HTML: ".html",
            CodeLanguage.CSS: ".css",
            CodeLanguage.JSON: ".json",
            CodeLanguage.YAML: ".yaml",
            CodeLanguage.TOML: ".toml",
            CodeLanguage.MARKDOWN: ".md",
            CodeLanguage.TEXT: ".txt",
        }.get(self.language, ".txt")

    def get_suggested_filename(self) -> str:
        """Get a suggested filename for the code archive.

        Returns:
            A suggested filename based on the title and language
        """
        # Convert title to a valid filename
        safe_title = re.sub(r"[^a-zA-Z0-9_\- ]", "", self.title)
        safe_title = re.sub(r"\s+", "_", safe_title).strip("_")

        if not safe_title:
            safe_title = "untitled"

        return f"{safe_title}{self.get_file_extension()}"

    def get_code_statistics(self) -> dict[str, int]:
        """Get statistics about the code.

        Returns:
            A dictionary with statistics like line count, word count, etc.
        """
        lines = self.content.splitlines()
        non_empty_lines = [line for line in lines if line.strip()]

        return {
            "total_lines": len(lines),
            "non_empty_lines": len(non_empty_lines),
            "empty_lines": len(lines) - len(non_empty_lines),
            "char_count": len(self.content),
            "word_count": len(self.content.split()),
        }

    def create_new_version(self, content: str | None = None, **updates: Any) -> CodeArchive:
        """Create a new version of the code archive.

        Args:
            content: New content for the version (if None, keeps current content)
            **updates: Other fields to update

        Returns:
            A new CodeArchive instance with an incremented version
        """
        # Create a copy of the current data
        data = self.model_dump()

        # Remove fields that shouldn't be copied
        for field in ["id", "created_at", "updated_at", "version"]:
            data.pop(field, None)

        # Update with new content and other updates
        if content is not None:
            data["content"] = content
        data.update(updates)

        # Set parent_id to the current archive's ID
        data["parent_id"] = self.id

        # Create the new version
        new_version = self.__class__(**data)

        # Bump the version if not explicitly set in updates
        if "version" not in updates:
            new_version.bump_version("patch")

        return new_version

    def is_update_needed(self, content: str) -> bool:
        """Check if the content has changed and an update is needed.

        Args:
            content: The new content to compare with the current content

        Returns:
            True if the content has changed, False otherwise
        """
        return self.content != content

    def __str__(self) -> str:
        """Return a string representation of the code archive."""
        return f"CodeArchive(id={self.id}, title='{self.title}', language={self.language}, version={self.version})"

    def __repr__(self) -> str:
        """Return a detailed string representation of the code archive."""
        return (
            f"CodeArchive(\n"
            f"    id='{self.id}',\n"
            f"    title='{self.title}',\n"
            f"    language={self.language},\n"
            f"    version='{self.version}',\n"
            f"    author_id='{self.author_id}',\n"
            f"    created_at={self.created_at.isoformat() if self.created_at else None},\n"
            f"    updated_at={self.updated_at.isoformat() if self.updated_at else None},\n"
            f"    is_archived={self.is_archived},\n"
            f"    tags={self.tags},\n"
            f"    visibility={self.visibility}\n"
            ")"
        )

    def update(self, **updates: Any) -> None:
        """Update the code archive with new values.

        Args:
            **updates: Dictionary of fields to update

        Note:
            Protected fields (id, created_at, author_id) cannot be updated
        """
        protected_fields = {"id", "created_at", "author_id"}
        model_fields = self.__class__.model_fields

        for field, value in updates.items():
            # Skip protected fields
            if field in model_fields and field not in protected_fields:
                setattr(self, field, value)

        # Always update the updated_at timestamp
        self.updated_at = datetime.now(timezone.utc)

    def add_tag(self, tag: str) -> None:
        """Add a tag to the code archive.

        Args:
            tag: Tag to add
        """
        if tag and tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag: str) -> bool:
        """Remove a tag from the code archive.

        Args:
            tag: Tag to remove

        Returns:
            bool: True if tag was removed, False otherwise
        """
        if tag in self.tags:
            self.tags.remove(tag)
            return True
        return False

    def add_dependency(self, dependency: str) -> None:
        """Add a dependency to the code archive.

        Args:
            dependency: Dependency to add (e.g., package name)
        """
        if dependency and dependency not in self.dependencies:
            self.dependencies.append(dependency)

    def remove_dependency(self, dependency: str) -> bool:
        """Remove a dependency from the code archive.

        Args:
            dependency: Dependency to remove

        Returns:
            bool: True if dependency was removed, False otherwise
        """
        if dependency in self.dependencies:
            self.dependencies.remove(dependency)
            return True
        return False

    def archive(self) -> None:
        """Mark the code archive as archived/read-only."""
        self.is_archived = True
        self.updated_at = datetime.now(timezone.utc)

    def unarchive(self) -> None:
        """Mark the code archive as not archived."""
        self.is_archived = False
        self.updated_at = datetime.now(timezone.utc)

    def fork(self, new_author_id: str, **updates: Any) -> CodeArchive:
        """Create a fork of this code archive.

        Args:
            new_author_id: ID of the user creating the fork
            **updates: Fields to update in the forked version

        Returns:
            A new CodeArchive instance representing the fork
        """
        fork_data = self.model_dump()
        fork_data.update(
            {
                "id": str(uuid4()),
                "parent_id": self.id,
                "author_id": new_author_id,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "version": "1.0.0",  # Reset version for the fork
            }
        )
        fork_data.update(updates)
        return CodeArchive.model_validate(fork_data)

    def to_json(self: CodeArchive, **kwargs: Any) -> str:
        """Convert the model to a JSON string.

        Args:
            **kwargs: Additional arguments to pass to model_dump_json.

        Returns:
            str: JSON string representation of the model.
        """
        return str(self.model_dump_json(**kwargs))

    @classmethod
    def from_json(cls: type[ModelT], json_str: str, **kwargs: Any) -> ModelT:
        """Create a CodeArchive from a JSON string.

        Args:
            json_str: JSON string to parse.
            **kwargs: Additional arguments to pass to model_validate_json.
        Returns:
            A new instance of the model class.
        """
        # Note: mypy can't verify the return type of model_validate_json,
        # but we know it returns an instance of the class
        return cls.model_validate_json(str(json_str), **kwargs)


def create_code_archive(
    content: str,
    language: CodeLanguage | str,
    title: str,
    author_id: str,
    **kwargs: Any,
) -> CodeArchive:
    """Create a new code archive with the given parameters.

    Args:
        content: The code content
        language: Programming language of the code
        title: Short title/name for the code snippet
        author_id: ID of the user creating the code
        **kwargs: Additional fields to set on the code archive

    Returns:
        A new CodeArchive instance
    """
    if isinstance(language, str):
        try:
            language = CodeLanguage(language.lower())
        except ValueError:
            language = CodeLanguage.OTHER

    return CodeArchive(
        content=content,
        language=language,
        title=title,
        author_id=author_id,
        **kwargs,
    )
